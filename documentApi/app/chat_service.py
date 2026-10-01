from __future__ import annotations

import hashlib
import json
import logging
import re
import time

from openai import OpenAI

from .chat_audit import ChatAudit
from .config import (
    _DEFAULT_SETTINGS,
    load_chat_settings,
    load_source_boosts,
    save_chat_settings as persist_chat_settings,
)
from .crypto_service import CryptoService
from .conversation_context import resolve_retrieval_context
from .evidence_selection import classify_query, select_evidence
from .grounding import PROMPT_VERSION, build_system_prompt, prepare_evidence, validate_and_render
from .models import AppSettings, ChatMessage, ChatRequest, ChatResponse, ChatSettings
from .services.thread_pool import run_in_worker_pool
from .vector_store.protocol import VectorStore
from .worker import embed_queries
from .wavelength_reasoning import compare_wavelength
from .reference_answers import answer_reference
from .literal_answers import answer_literal
from .semantic_support import entails, available as semantic_available, REVISION as SEMANTIC_REVISION
from .operational_answers import answer_operational
from .sourced_procedures import answer_procedure
from .component_tables import answer_component_table


_MAX_QUERY_CHARS = 8_000
_MAX_HISTORY_MESSAGES = 20
_MAX_HISTORY_CHARS = 40_000

_logger = logging.getLogger(__name__)


def _bounded_history(history: list[ChatMessage]) -> list[ChatMessage]:
    selected: list[ChatMessage] = []
    remaining_chars = _MAX_HISTORY_CHARS

    for message in reversed(history[-_MAX_HISTORY_MESSAGES:]):
        content = message.content.strip()
        if not content:
            continue
        if len(content) > remaining_chars:
            content = content[-remaining_chars:]
        selected.append(message.model_copy(update={"content": content}))
        remaining_chars -= len(content)
        if remaining_chars == 0:
            break

    selected.reverse()
    if selected and selected[0].role == "assistant":
        selected.pop(0)
    return selected


class ChatService:
    def __init__(
        self,
        vector_service: VectorStore,
        crypto_service: CryptoService,
        audit: ChatAudit | None = None,
    ) -> None:
        self._vs = vector_service
        self._crypto = crypto_service
        self._audit = audit
        self._settings: AppSettings = _DEFAULT_SETTINGS.model_copy(deep=True)
        self._chat_settings = load_chat_settings()

    def update_settings(self, app_settings: AppSettings) -> None:
        self._settings = app_settings

    def set_vector_store(self, vector_service: VectorStore) -> None:
        """Muss nach IngestService._rebuild_vector_store() aufgerufen werden (gleiche DB-Datei / gleicher Store)."""
        self._vs = vector_service

    def get_chat_settings(self) -> ChatSettings:
        return self._chat_settings

    def update_chat_settings(self, chat_settings: ChatSettings) -> None:
        self._chat_settings = persist_chat_settings(chat_settings)

    def _record(self, trace: dict, private: dict) -> None:
        if self._audit is not None:
            try:
                trace["auditStored"] = True
                self._audit.append(trace, private)
            except Exception:
                trace["auditStored"] = False
                _logger.exception("encrypted chat audit write failed")
        else:
            trace["auditStored"] = False
        _logger.info("chat_trace %s", json.dumps(trace, sort_keys=True))

    async def chat(self, request: ChatRequest) -> ChatResponse:
        started_at = time.perf_counter()
        query = request.message.strip()[:_MAX_QUERY_CHARS]
        history = _bounded_history(request.history or [])
        history_payload = [msg.model_dump(by_alias=True) for msg in history]
        retrieval_context = resolve_retrieval_context(query, history_payload)
        retrieval_query = retrieval_context.query
        preferred_language = request.language
        active_pg = self._settings.get_active_postgres()
        index_id = f"{active_pg.environment_id}:{active_pg.vector_backend}:{active_pg.db_schema}.{active_pg.db_table_name}"

        if retrieval_context.resolution in ("ambiguous", "unresolved"):
            answer = ("Welches Instrument meinst du? Bitte nenne es explizit."
                      if preferred_language == "de" else
                      "Which instrument do you mean? Please name it explicitly.")
            elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
            trace = {"promptVersion": PROMPT_VERSION, "promptSha256": "", "model": self._chat_settings.llm_model,
                     "embeddingModel": self._settings.embedding_model, "corpusVersion": "unknown", "indexId": index_id,
                     "retrievalScores": [], "contextResolution": retrieval_context.resolution,
                     "abstained": True, "elapsedMs": elapsed_ms, "embeddingMs": 0, "retrievalMs": 0,
                     "generationMs": 0, "validationMs": 0, "generationAttempts": 0,
                     "promptTokens": 0, "completionTokens": 0, "totalTokens": 0}
            private = {"query": query, "retrievalQuery": retrieval_query, "history": history_payload,
                       "context_chunks": [], "answer": answer}
            self._record(trace, private)
            return ChatResponse(answer=answer, context_chunks=[], encrypted_payload=self._crypto.encrypt_json(private),
                                metrics={"elapsedMs": elapsed_ms, "abstained": True}, trace=trace)

        query_embedding = await run_in_worker_pool(
            embed_queries, self._settings.embedding_model, [retrieval_query]
        )
        if not query_embedding.get("ok") or not query_embedding.get("vectors"):
            elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
            trace = {"promptVersion": PROMPT_VERSION, "promptSha256": "", "model": self._chat_settings.llm_model,
                     "embeddingModel": self._settings.embedding_model, "corpusVersion": "unknown", "indexId": index_id,
                     "retrievalScores": [], "abstained": True, "elapsedMs": elapsed_ms, "embeddingMs": elapsed_ms,
                     "retrievalMs": 0, "generationMs": 0, "validationMs": 0,
                     "promptTokens": 0, "completionTokens": 0, "totalTokens": 0, "embeddingFailed": True,
                     "contextResolution": retrieval_context.resolution}
            self._record(trace, {"query": query, "retrievalQuery": retrieval_query,
                                 "history": history_payload, "embeddingFailed": True})
            return ChatResponse(
                answer="Embedding der Anfrage fehlgeschlagen." if preferred_language=='de' else "The query could not be embedded. Please retry.",
                context_chunks=[],
                encrypted_payload="",
                metrics={"elapsedMs": elapsed_ms, "abstained": True},
                trace=trace,
            )

        embedding_ms = max(1, int((time.perf_counter() - started_at) * 1000))
        query_vector = query_embedding["vectors"][0]

        # Retrieve a wider candidate pool, then rerank for QA precision.
        candidate_k = max(self._chat_settings.top_k, min(max(self._chat_settings.top_k * 8, 40), 120))
        candidate_chunks = self._vs.similarity_search(
            table_name=active_pg.db_table_name,
            query_vector=query_vector,
            top_k=candidate_k,
        )

        # Broad instrument questions need the reference overview even when vector
        # similarity favors filter tables or old design reports. This retrieves
        # corpus evidence, not a hard-coded answer, and retains the similarity floor.
        intent = classify_query(retrieval_query)
        if re.search(r'\bgrism\b|\bG#\d+',retrieval_query,re.I) and not intent.instruments:
            candidate_chunks.extend(self._vs.search_by_filename(
                table_name=active_pg.db_table_name,pattern='-grisms.md',query_vector=query_vector,top_k=256))
        if intent.instruments:
            existing = {(c["documentId"], c["chunkIndex"]) for c in candidate_chunks}
            for instrument in sorted(intent.instruments):
                # Source anchors are evidence routes, never answer templates.
                # The landing page filename does not include 'overview'.
                patterns = (f"instruments-{instrument.lower()}.md",
                            f"instruments-{instrument.lower()}-overview",
                            f"cookbook-php-instrument-{instrument.lower()}")
                if re.search(r'\bgrism\b|\bG#\d+',retrieval_query,re.I):
                    patterns+=(f'instruments-{instrument.lower()}-grisms.md',)
                if re.search(r'\bcommand\b',retrieval_query,re.I):
                    patterns+=('sequencer_reference.md',)
                for pattern in patterns:
                    command_catalog = pattern == 'sequencer_reference.md'
                    component_catalog = pattern.endswith('-grisms.md')
                    setting_table = 'cookbook' in pattern and bool(re.search(r'\b[a-z]+(?:-[a-z]+)+\b',retrieval_query,re.I))
                    reference_inventory = ("cookbook" in pattern and re.search(r"\bfib(?:er|re)s?\b", retrieval_query,re.I)
                                           and re.search(r"how many|resolution|resolving|diameter|aperture|size|used for",retrieval_query,re.I))
                    anchored = self._vs.search_by_filename(
                        table_name=active_pg.db_table_name, pattern=pattern,
                        query_vector=query_vector, top_k=2048 if command_catalog else 256 if reference_inventory or setting_table or component_catalog else 4,
                    )
                    for chunk in anchored:
                        if setting_table and not reference_inventory:
                            fields=re.findall(r'\b[a-z]+(?:-[a-z]+)+\b',retrieval_query.lower())
                            tables=chunk.get('completeTables',[])
                            if any(all(re.search(r'(?<!\w)'+re.escape(f)+r'(?!\w)',table,re.I) for f in fields)
                                   and re.search(r'^\|\s*instrument\s*\|',table,re.I|re.M) for table in tables):
                                chunk={**chunk,'exactReference':True}
                            elif chunk not in anchored[:4]:
                                continue
                        if command_catalog:
                            from .source_policy import annotate_source
                            chunk=annotate_source(chunk)
                            command=str(chunk.get('section','')).strip('` ')
                            if (chunk.get('instrument','').upper()!=instrument
                                    or not re.fullmatch(r'[a-z][a-z0-9_.-]+',command,re.I)
                                    or not re.search(r'(?<!\w)'+re.escape(command)+r'(?!\w)',retrieval_query,re.I)):
                                continue
                            chunk={**chunk,'exactReference':True}
                        if reference_inventory:
                            from .table_facts import derived_facts
                            from .source_policy import annotate_source
                            candidate = annotate_source(chunk)
                            if candidate.get("status") not in ("active","current"):
                                continue
                            if any(fact["entity"] == "fiber" for table in chunk.get("completeTables",[]) for fact in derived_facts(table)):
                                chunk = {**chunk,"referenceInventory":True}
                            elif chunk not in anchored[:4]:
                                continue
                        key = (chunk["documentId"], chunk["chunkIndex"])
                        if key not in existing:
                            candidate_chunks.append(chunk)
                            existing.add(key)
                        elif chunk.get("referenceInventory") or chunk.get('exactReference'):
                            for existing_chunk in candidate_chunks:
                                if (existing_chunk["documentId"],existing_chunk["chunkIndex"]) == key:
                                    if chunk.get('referenceInventory'):
                                        existing_chunk['referenceInventory'] = True
                                    if chunk.get('exactReference'):
                                        existing_chunk['exactReference'] = True

        # Data handling is a documented operating domain. Its instrument
        # cookbook entries are only pointers; retrieve the indexed shared guide,
        # never fetch arbitrary links or insert an answer from a template.
        if re.search(r'\bdata\b', retrieval_query, re.I) and re.search(
                r'\b(?:download\w*|shar\w*|access|team|server|principal investigator|PI)\b', retrieval_query, re.I):
            existing = {(c['documentId'], c['chunkIndex']) for c in candidate_chunks}
            for chunk in self._vs.search_by_filename(
                    table_name=active_pg.db_table_name, pattern='observing-tools-datadownload-html.md',
                    query_vector=query_vector, top_k=8):
                if (chunk['documentId'], chunk['chunkIndex']) not in existing:
                    candidate_chunks.append(chunk)
                    existing.add((chunk['documentId'], chunk['chunkIndex']))

        # General telescope specifications have no instrument tag; explicitly
        # include their indexed reference for technical-property questions.
        if (not intent.instruments and re.search(r'\btelescope\b',retrieval_query,re.I)
                and re.search(r'\b(?:scale|field|aperture|weight|diameter|focus|focal)\b',retrieval_query,re.I)):
            candidate_chunks.extend(self._vs.search_by_filename(
                table_name=active_pg.db_table_name,pattern='telescope-technical-details-html.md',
                query_vector=query_vector,top_k=6))

        # Follow documentation references only to an already-indexed official
        # source. No network fetch, arbitrary host or document instruction can
        # cause an external request. Link labels must match the actual topic.
        from .linked_references import matching_reference_links
        for pattern,url in matching_reference_links(retrieval_query,candidate_chunks):
            for linked in self._vs.search_by_filename(
                    table_name=active_pg.db_table_name,pattern=pattern,query_vector=query_vector,top_k=3):
                from .linked_references import canonical_key
                if canonical_key(linked.get('canonicalLocation','')) == canonical_key(url):
                    candidate_chunks.append({**linked,'linkedReference':True})

        # Scoped technical/policy lookups must not stop at a report introduction.
        # Expand only topic-matched indexed sources, not the whole corpus.
        from .reference_focus import focused_sources, property_match
        for filename in focused_sources(retrieval_query, candidate_chunks):
            scoped_chunks = self._vs.search_by_filename(
                    table_name=active_pg.db_table_name, pattern=filename,
                    query_vector=query_vector, top_k=256)
            from .grounding import _identifier_numbers
            scope_ids = sorted(_identifier_numbers(' '.join(c.get('text','') for c in scoped_chunks)))
            for chunk in scoped_chunks:
                if property_match(retrieval_query, chunk.get('text', '')):
                    candidate_chunks.append({**chunk, 'exactReference': True, 'focusedReference': True,
                                             'focusedScopeIdentifiers': scope_ids})

        # Exact numbered-table routes use source structure, not embeddings alone:
        # a requested component can be far down a long table whose prose does
        # not contain the component's nickname from the question.
        component=re.search(r'\bgrism\s*(?:#|number\s*)?(\d+)\b|\bG#(\d+)\b',retrieval_query,re.I)
        if component:
            identifier=component[1] or component[2]
            properties=[p for p in ('central','dispersion','resolution') if re.search(r'\b'+p+r'\b',retrieval_query,re.I)]
            for chunk in candidate_chunks:
                if properties and any(all(p in table.lower() for p in properties)
                                      and re.search(r'^\|\s*'+re.escape(identifier)+r'(?:\s+[a-z])?\s*\|',table,re.I|re.M)
                                      for table in chunk.get('completeTables',[])):
                    chunk['exactReference']=True

        # Guarantee every *effectively* boosted source appears in the candidate pool.
        # Only patterns with multiplier != 1.0 are considered — weight=1.0 is a no-op
        # and must not alter the candidate set (preserves identical behavior to pre-boost).
        # Matches the same filtering applied during evidence selection.
        #
        # Safety cap: injected extra chunks are limited to top_k // 3 sources (min 1).
        # This prevents a large number of boosted-but-irrelevant sources from consuming
        # the entire context window and degrading answers for unrelated queries.
        boosts = load_source_boosts()
        effective_boosts = {k: v for k, v in boosts.items() if v != 1.0}
        if effective_boosts:
            represented = {c["fileName"].lower() for c in candidate_chunks}
            inject_cap = max(1, self._chat_settings.top_k // 3)
            injected = 0
            for pattern in effective_boosts:
                if injected >= inject_cap:
                    break
                if not any(pattern in fname for fname in represented):
                    extra = self._vs.search_by_filename(
                        table_name=active_pg.db_table_name,
                        pattern=pattern,
                        query_vector=query_vector,
                        top_k=2,
                    )
                    if extra:
                        candidate_chunks.extend(extra)
                        injected += 1

        context_chunks = select_evidence(
            query=retrieval_query,
            chunks=candidate_chunks,
            top_k=self._chat_settings.top_k,
            source_boosts=boosts,
            max_chunks_per_source=self._chat_settings.max_chunks_per_source,
            min_similarity=self._chat_settings.min_evidence_similarity,
        )

        # Complete an interrupted procedure/table within its own section and
        # version, with a bounded two-chunk allowance. Never cross into a spare
        # configuration, a new topic, or an inactive source version.
        expanded = []
        seen = {(c["documentId"], c["chunkIndex"]) for c in context_chunks}
        inspected = set()
        from .source_policy import annotate_source
        for selected in context_chunks:
            if len(expanded) >= 2:
                break
            structured = bool(set(selected.get("contentTypes", [])) & {"table", "list", "code", "warning"})
            doc_id = selected["documentId"]
            if doc_id in inspected:
                continue
            inspected.add(doc_id)
            neighbors = self._vs.search_by_filename(
                table_name=active_pg.db_table_name, pattern=selected["fileName"],
                query_vector=query_vector, top_k=256,
            )
            for neighbor in sorted(neighbors, key=lambda c: abs(c["chunkIndex"]-selected["chunkIndex"])):
                key = (neighbor["documentId"], neighbor["chunkIndex"])
                neighbor = annotate_source(neighbor)
                headings = selected.get("headingPath", [])
                neighbor_headings = neighbor.get("headingPath", [])
                same_section = structured and neighbor_headings == headings
                child_table = (headings and neighbor_headings[:len(headings)] == headings
                               and bool(neighbor.get("completeTables"))
                               and neighbor.get("status") == selected.get("status"))
                if (key in seen or neighbor["documentId"] != doc_id
                        or abs(neighbor["chunkIndex"]-selected["chunkIndex"]) != 1
                        or not (same_section or child_table)
                        or neighbor.get("contentTypes") == ["heading"]):
                    continue
                from .evidence_selection import _duplicate_key, _near_duplicate
                if any(_duplicate_key(neighbor) == _duplicate_key(other)
                       or _near_duplicate(neighbor.get('text', ''), other.get('text', ''))
                       for other in [*context_chunks, *expanded]):
                    continue
                expanded.append({**neighbor, "neighborExpansion": True})
                seen.add(key)
                if len(expanded) >= 2:
                    break
        context_chunks.extend(expanded)

        retrieval_ms = max(1, int((time.perf_counter() - started_at) * 1000) - embedding_ms)
        corpus_versions = sorted({str(c.get("corpusVersion", "")) for c in context_chunks if c.get("corpusVersion")})
        trace_base = {
            "promptVersion": PROMPT_VERSION,
            "model": self._chat_settings.llm_model,
            "embeddingModel": self._settings.embedding_model,
            "corpusVersion": ",".join(corpus_versions) or "unknown",
            "indexId": index_id,
            "retrievalScores": [
                {"documentId": c.get("documentId", ""), "chunkIndex": c.get("chunkIndex", 0),
                 "similarity": c.get("similarity", 0), "score": c.get("retrievalScore", 0)}
                for c in context_chunks
            ],
            "embeddingMs": embedding_ms,
            "retrievalMs": retrieval_ms,
            "contextResolution": retrieval_context.resolution,
        }

        if not context_chunks:
            german = preferred_language == "de" or (
                preferred_language is None
                and bool(re.search(r"[äöüß]|\b(?:wie|wo|warum|welche|welcher|kann|ich|nicht|für)\b", query, re.I))
            )
            answer = (
                "Ich konnte im aktiven Dokumentenbestand keine ausreichenden Belege für diese Frage finden."
                if german else
                "I could not find documentation supporting this question in the active corpus."
            )
            elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
            trace = {**trace_base, "promptSha256": "", "abstained": True, "elapsedMs": elapsed_ms,
                     "generationMs": 0, "validationMs": 0, "promptTokens": 0, "completionTokens": 0, "totalTokens": 0}
            private = {"query": query, "retrievalQuery": retrieval_query,
                       "history": history_payload, "context_chunks": [], "answer": answer}
            self._record(trace, private)
            return ChatResponse(
                answer=answer,
                context_chunks=[],
                encrypted_payload=self._crypto.encrypt_json(private),
                metrics={"elapsedMs": elapsed_ms, "abstained": True},
                trace=trace,
            )

        evidence, context_chunks = prepare_evidence(context_chunks)
        for score, chunk in zip(trace_base["retrievalScores"], context_chunks):
            score["citationId"] = chunk["citationId"]

        german = preferred_language == "de" or (
            preferred_language is None
            and bool(re.search(r"[äöüß]|\b(?:wie|wo|warum|welche|welcher|kann|ich|nicht|für)\b", query, re.I))
        )
        answer_language = "de" if german else "en"
        if preferred_language == "de":
            language_instruction = (
                "MANDATORY OUTPUT LANGUAGE: German (Deutsch). "
                "Your entire final answer MUST be in German only."
            )
            language_user_suffix = "WICHTIG: Antworte ausschliesslich auf Deutsch."
        elif preferred_language == "en":
            language_instruction = (
                "MANDATORY OUTPUT LANGUAGE: English. "
                "Your entire final answer MUST be in English only."
            )
            language_user_suffix = "IMPORTANT: Reply strictly in English only."
        else:
            language_instruction = "Respond in the same language as the user's question."
            language_user_suffix = ""

        system_prompt = build_system_prompt(
            self._chat_settings.system_prompt, language_instruction, evidence
        )
        if retrieval_context.resolution == "inherited":
            system_prompt += (
                "\nThe user's current instrument reference resolves to "
                + next(iter(retrieval_context.instruments))
                + ". Use chat history only to interpret the question, never as factual evidence."
            )
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        user_content = query if not language_user_suffix else f"{query}\n\n{language_user_suffix}"
        user_content += "\nReturn the required JSON claim/evidence object, answering this question rather than a related question."
        if re.search(r"\bused for\b|\bcapabilities\b", retrieval_query, re.I):
            user_content += " State the supported observing capabilities/modes, not just an instrument definition."
        if "procedure" in intent.categories or re.search(r"\bsequence\b|\bsteps\b", retrieval_query, re.I):
            user_content += " Include the complete ordered procedure supported by the evidence; do not omit prerequisite or recovery steps."
        messages.append({"role": "user", "content": user_content})
        prompt_hash = hashlib.sha256(
            json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        generation_started = time.perf_counter()
        raw_answer = ""
        error_type = ""
        checked_answer = (answer_operational(retrieval_query, evidence, answer_language)
                          or answer_procedure(retrieval_query,evidence,answer_language)
                          or answer_reference(retrieval_query, evidence, answer_language)
                          or answer_component_table(retrieval_query,evidence,answer_language)
                          or compare_wavelength(retrieval_query, evidence, answer_language)
                          or answer_literal(retrieval_query, evidence, answer_language))
        prompt_tokens = completion_tokens = total_tokens = 0
        if checked_answer is None:
            try:
                client = OpenAI(
                    api_key=self._chat_settings.llm_api_key,
                    base_url=self._chat_settings.llm_base_url or None,
                )
                completion = await run_in_worker_pool(
                    client.chat.completions.create,
                    model=self._chat_settings.llm_model,
                    messages=messages,
                    temperature=self._chat_settings.temperature,
                    max_tokens=self._chat_settings.max_tokens,
                    response_format={"type": "json_object"},
                )
                raw_answer = completion.choices[0].message.content or ""
                usage = getattr(completion, "usage", None)
                prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
                total_tokens = int(getattr(usage, "total_tokens", 0) or 0)
            except Exception as exc:
                error_type = type(exc).__name__
                _logger.exception("chat model request failed")
        generation_ms = max(1, int((time.perf_counter() - generation_started) * 1000)) if checked_answer is None else 0

        validation_started = time.perf_counter()
        validation = checked_answer.validation if checked_answer else await run_in_worker_pool(
            validate_and_render, raw_answer, evidence, answer_language,
            historical_intent=intent.historical or "technical_reference" in intent.categories,
            question=retrieval_query, semantic_check=entails,
        )
        validation_ms = max(1, int((time.perf_counter() - validation_started) * 1000))
        initial_validation = validation
        generation_attempts = 0 if checked_answer else 1
        model_outputs = [] if checked_answer else [raw_answer]
        if validation.rejected_claims > 0 and not error_type:
            # Repair a failed structured response once. Do not retry deliberate
            # empty-claims abstentions, and validate the correction identically.
            messages.extend([
                {"role": "assistant", "content": raw_answer},
                {"role": "user", "content": (
                    "Your claims failed citation/support validation. Return a corrected JSON object. "
                    + "Rejected checks: " + ", ".join(validation.rejection_reasons) + ". " +
                    "Use concise complete sentences closely following the supplied evidence. "
                    "Do not expand acronyms or add unsupported wording. For each claim use one brief "
                    "exact quote copied from its cited evidence, preserving numbers, units and punctuation. "
                    "Identifiers and dates in the user's question are not evidence: omit their restatement "
                    "if your cited item does not establish them. Still report requested values that the "
                    "source does establish, naming the documented subject rather than inventing its identity. "
                    "Remove claims you cannot support; if none remain, return {\"claims\":[]}."
                )},
            ])
            prompt_hash = hashlib.sha256(
                json.dumps(messages, ensure_ascii=False, sort_keys=True).encode("utf-8")
            ).hexdigest()
            retry_started = time.perf_counter()
            generation_attempts = 2
            try:
                completion = await run_in_worker_pool(
                    client.chat.completions.create,
                    model=self._chat_settings.llm_model,
                    messages=messages,
                    temperature=self._chat_settings.temperature,
                    max_tokens=self._chat_settings.max_tokens,
                    response_format={"type": "json_object"},
                )
                raw_answer = completion.choices[0].message.content or ""
                model_outputs.append(raw_answer)
                usage = getattr(completion, "usage", None)
                prompt_tokens += int(getattr(usage, "prompt_tokens", 0) or 0)
                completion_tokens += int(getattr(usage, "completion_tokens", 0) or 0)
                total_tokens += int(getattr(usage, "total_tokens", 0) or 0)
            except Exception as exc:
                error_type = type(exc).__name__
                _logger.exception("chat model correction request failed")
            generation_ms += max(1, int((time.perf_counter() - retry_started) * 1000))
            validation_started = time.perf_counter()
            corrected = await run_in_worker_pool(validate_and_render,
                raw_answer, evidence, answer_language, historical_intent=intent.historical or "technical_reference" in intent.categories,
                question=retrieval_query, semantic_check=entails,
            )
            # A failed correction must not erase already verified facts.
            if not corrected.abstained or validation.abstained:
                validation=corrected
            validation_ms += max(1, int((time.perf_counter() - validation_started) * 1000))
        if validation.abstained and checked_answer is None:
            from .source_excerpts import answer_excerpt
            excerpt=answer_excerpt(retrieval_query,evidence,answer_language)
            if excerpt:
                checked_answer=excerpt
                validation=excerpt.validation
        answer = validation.answer
        if error_type:
            answer = (
                "Das Antwortmodell ist derzeit nicht verfügbar. Bitte versuche es erneut."
                if german else "The answer model is currently unavailable. Please retry."
            )
        elapsed_ms = max(1, int((time.perf_counter() - started_at) * 1000))
        abstained = validation.abstained or bool(error_type)
        tokens_per_second = (
            round(completion_tokens / (generation_ms / 1000.0), 2)
            if completion_tokens > 0 else 0.0
        )
        trace = {
            **trace_base,
            "promptSha256": prompt_hash,
            "abstained": abstained,
            "elapsedMs": elapsed_ms,
            "generationMs": generation_ms,
            "validationMs": validation_ms,
            "promptTokens": prompt_tokens,
            "completionTokens": completion_tokens,
            "totalTokens": total_tokens,
            "acceptedClaims": validation.accepted_claims,
            "rejectedClaims": validation.rejected_claims,
            "resolvedExcerpts": validation.resolved_excerpts,
            "invalidCitations": validation.invalid_citations,
            "generationAttempts": generation_attempts,
            "initialRejectedClaims": initial_validation.rejected_claims,
            "initialInvalidCitations": initial_validation.invalid_citations,
            "rejectionReasons": list(validation.rejection_reasons),
            "initialRejectionReasons": list(initial_validation.rejection_reasons),
            "abstentionReason": ("model_unavailable" if error_type else "claim_validation_failed" if validation.rejected_claims else "model_found_no_support") if abstained else None,
            "answerMethod": checked_answer.derivation["operation"] if checked_answer else "validated-model-claims",
            "semanticChecker": "local-nli-" + SEMANTIC_REVISION if not checked_answer and semantic_available() else "deterministic",
        }
        if error_type:
            trace["generationErrorType"] = error_type
        private_payload = {
            "query": query,
            "retrievalQuery": retrieval_query,
            "context_chunks": context_chunks,
            "history": [msg.model_dump(by_alias=True) for msg in history],
            "prompt": system_prompt,
            "promptVersion": PROMPT_VERSION,
            "rawModelOutput": raw_answer,
            "modelOutputs": model_outputs,
            "messages": messages,
            "answer": answer,
        }
        if checked_answer:
            private_payload["derivation"] = checked_answer.derivation
        self._record(trace, private_payload)
        encrypted_payload = self._crypto.encrypt_json(private_payload)
        return ChatResponse(
            answer=answer,
            context_chunks=context_chunks,
            encrypted_payload=encrypted_payload,
            metrics={
                "elapsedMs": elapsed_ms,
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "totalTokens": total_tokens,
                "tokensPerSecond": tokens_per_second,
                "abstained": abstained,
            },
            trace=trace,
        )
