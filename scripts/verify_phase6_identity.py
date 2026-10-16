#!/usr/bin/env python3
"""Public release configuration identity; never export keys or prompt bodies."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.request import Request,urlopen
sys.path.insert(0,'/app')
from app.config import load_chat_settings,load_settings
from app.semantic_support import MODEL,REVISION


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    app=load_settings(); chat=load_chat_settings(); pg=app.get_active_postgres()
    public={'indexId':f'{pg.environment_id}:{pg.vector_backend}:{pg.db_schema}.{pg.db_table_name}',
            'embeddingModel':app.embedding_model,'llmModel':chat.llm_model,
            'temperature':chat.temperature,'maxTokens':chat.max_tokens,'topK':chat.top_k,
            'maxChunksPerSource':chat.max_chunks_per_source,'minEvidenceSimilarity':chat.min_evidence_similarity,
            'systemPromptSha256':hashlib.sha256(chat.system_prompt.encode()).hexdigest(),
            'semanticVerifier':{'model':MODEL,'revision':REVISION,'device':'cpu','localOnly':True},
            'embeddingRevision':'b33106f585b9ce46904ad7443a3b52b7a63e231c'}
    base=chat.llm_base_url.rstrip('/').removesuffix('/v1')
    def call(path,data=None):
        req=Request(base+path,data=json.dumps(data).encode() if data else None,headers={'Content-Type':'application/json'})
        with urlopen(req,timeout=60) as response:
            return json.load(response)
    tag=next(m for m in call('/api/tags')['models'] if m['name']==chat.llm_model)
    show=call('/api/show',{'model':chat.llm_model})
    weight=re.search(r'(?m)^FROM .*sha256-([a-f0-9]{64})\s*$',show.get('modelfile',''))
    context=re.search(r'(?m)^num_ctx\s+(\d+)\s*$',show.get('parameters',''))
    public['ollamaProfile']={'digest':tag['digest'],'weightsSha256':weight[1] if weight else None,
                            'numCtx':int(context[1]) if context else None,'details':tag.get('details')}
    receipt={'verifiedAt':datetime.now(timezone.utc).isoformat(),'configuration':public,
             'publicConfigurationSha256':hashlib.sha256(json.dumps(public,sort_keys=True).encode()).hexdigest(),
             'scope':'Whitelisted operational configuration only; keys, endpoint credentials, prompt bodies and audits excluded'}
    args.output.write_text(json.dumps(receipt,indent=2)+'\n'); print(json.dumps(receipt))


if __name__=='__main__':
    main()
