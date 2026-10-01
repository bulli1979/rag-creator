import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "documentApi"))
from app.conversation_context import resolve_retrieval_context
from app.document_processing import structured_chunks,scrub_sensitive_text,markdown_blocks
from app.grounding import prepare_evidence, validate_and_render
from app.html_processing import html_to_markdown, meaningful_title
from app.source_policy import annotate_source
from app.reference_answers import answer_reference
from app.literal_answers import answer_literal
from app.operational_answers import answer_operational
from app.sourced_procedures import answer_procedure
from app.linked_references import matching_reference_links,canonical_key
from app.component_tables import answer_component_table
from app.source_excerpts import answer_excerpt
from app.reference_focus import focused_sources, property_match


class RecoveryTests(unittest.TestCase):
    def test_road_advisory_preserves_current_condition_check_and_reads_times(self):
        query='During winter, what hours should visitors avoid using the mountain road?'
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','sourceRole':'operator_guide','status':'active',
              'content':'Note that in the winter period additional procedures apply. You are advised not to travel on the mountain road before 10:15 or after 17:45. In any case always contact Reception for the latest road and weather conditions before travelling. Unrelated phone numbers follow.'}
        answer=answer_operational(query,[item])
        self.assertIn('10:15',answer.validation.answer)
        self.assertIn('17:45',answer.validation.answer)
        self.assertIn('always contact Reception',answer.validation.answer)
        self.assertNotIn('Unrelated phone',answer.validation.answer)
        self.assertIsNone(answer_operational(query,[{**item,'status':'historical'}]))
        self.assertIsNone(answer_operational(query,[{**item,'content':item['content'].split('In any case')[0]}]))
        self.assertIsNone(answer_operational(query.replace('winter','summer'),[item]))
    def test_troubleshooting_does_not_drop_specific_error_prerequisite(self):
        query='What should an observer do if the ALFOSC UIF fails to start with an error message?'
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','instrument':'ALFOSC','sourceRole':'operator_guide',
              'status':'active','content':'* **ALFOSC UIF fails with "Service handoff failed.":**\n  + Power cycle the controller and try again\n* Another unrelated problem.'}
        answer=answer_operational(query,[item])
        self.assertTrue(answer.validation.abstained)
        self.assertIn('exact error message',answer.validation.answer)
        self.assertNotIn('Power cycle',answer.validation.answer)
        self.assertIsNone(answer_operational(query+' It says "Service handoff failed."',[item]))
        evidence,_=prepare_evidence([{'documentId':'a'*64,'chunkIndex':0,'text':item['content']}])
        raw=json.dumps({'claims':[{'text':'Power cycle the controller and try again.',
                                  'evidence':[{'citationId':'S1','quote':'Power cycle the controller and try again'}]}]})
        result=validate_and_render(raw,evidence,question=query,semantic_check=lambda *args:True)
        self.assertTrue(result.abstained)
        self.assertIn('missing_troubleshooting_condition',result.rejection_reasons)
    def test_named_detector_pixel_dimensions_require_product_and_complete_units(self):
        query='What is the physical pixel size (in microns) of the SITe SI-987A CCD?'
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','status':'active','title':'Product datasheet',
              'content':'Pixel Size 17 µm x 18 µm\nTABLE 1 Device specifications, SI-987A'}
        answer=answer_literal(query,[item])
        self.assertIn('17 µm x 18 µm',answer.validation.answer)
        self.assertIsNone(answer_literal(query,[{**item,'content':item['content'].replace('SI-987A','SI-003A')}]))
        self.assertIsNone(answer_literal(query,[{**item,'content':item['content'].replace('µm','µ')}]))
        self.assertIsNone(answer_literal(query,[{**item,'content':'Pixel Size 17 µm x 18 µm\n[SI-987A](datasheet.pdf)'}]))
        self.assertIsNone(answer_literal(query,[{**item,'status':'historical'}]))
        self.assertIsNone(answer_literal(query,[{**item,'content':item['content']+' Also SI-999A.'}]))
    def test_frequency_lookup_preserves_assumptions_and_subject(self):
        query='What is the fundamental frequency of the pick-up noise observed with the ALFOSC controller?'
        chunk={'fileName':'arbitrary.md','title':'ALFOSC controller test report',
               'instrument':'ALFOSC','headingPath':['Pick-up noise'],'text':'A measurement of controller pick-up noise.'}
        self.assertEqual(focused_sources(query,[chunk]),['arbitrary.md'])
        self.assertEqual(focused_sources(query,[{**chunk,'instrument':'FIES'}]),[])
        self.assertEqual(focused_sources(query,[{**chunk,'instrument':'GENERAL'}]),['arbitrary.md'])
        item={'focusedReference':True,'citationId':'D-aaaaaaaaaaaaaaaa-C1','instrument':'ALFOSC',
              'sourceRole':'design_reference','section':'Pick-up noise',
              'content':'From analysis of raw pixel data the fundamental frequency of the noise is 12.34KHz (assuming the readout speeds are precise). There is no obvious explanation for this frequency. Tests involved disconnecting mains earth.'}
        for spelling in ('pick-up','pick up','pickup'):
            answer=answer_literal(query.replace('pick-up',spelling),[item])
            self.assertIn('12.34KHz',answer.validation.answer)
            self.assertIn('assuming the readout speeds are precise',answer.validation.answer)
            self.assertIn('not current operating guidance',answer.validation.answer)
            self.assertNotIn('mains earth',answer.validation.answer)
        self.assertIsNone(answer_literal(query,[{**item,'instrument':'FIES'}]))
        untagged={**item,'instrument':'GENERAL','title':'ALFOSC controller report'}
        self.assertIn('12.34',answer_literal(query,[untagged]).validation.answer)
        self.assertIsNone(answer_literal(query,[{**untagged,'title':'Detector report'}]))
        self.assertIsNone(answer_literal(query+' for CCD99',[item]))
        self.assertIsNone(answer_literal(query,[{**item,'content':item['content'].replace('12.34KHz','12.34')}]))
        self.assertIsNone(answer_literal(query.replace('pick-up','readout'),[item]))
        self.assertIsNone(answer_literal('How should I repair the ALFOSC pick-up noise fundamental frequency?',[item]))
        self.assertIsNone(answer_literal(query,[{**item,'section':'Readout noise'}]))
    def test_procedure_extraction_does_not_cross_an_explicit_instrument(self):
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','sourceRole':'operator_guide','status':'active',
              'instrument':'ALFOSC','sectionBoundariesKnown':True,'contentTypes':['paragraph'],
              'content':'During an OB identify the target with a+q, then identify it again on another image. Confirm the slit image twice.'}
        self.assertIsNotNone(answer_procedure('How do I identify the ALFOSC target in an OB?',[item]))
        self.assertIsNone(answer_procedure('How do I identify the FIES target in an OB?',[item]))
    def test_report_speeds_preserve_values_and_require_same_document_identity(self):
        item={'focusedReference':True,'focusedScopeIdentifiers':['3'],'citationId':'D-aaaaaaaaaaaaaaaa-C1',
              'sourceRole':'design_reference','content':'The new detector controller provides 4 speeds (100, 250, 450 and 900 kpix/sec).'}
        result=answer_literal('What readout speeds did the ALFOSC CCD3 controller report provide?',[item])
        self.assertIn('100, 250, 450 and 900',result.validation.answer)
        self.assertIn('not current operating guidance',result.validation.answer)
        incomplete={**item,'content':'At different readout speeds the gain varies. The fast test used 900 kpix/sec.'}
        self.assertIsNone(answer_literal('What readout speeds did the ALFOSC CCD3 controller report provide?',[incomplete]))
        self.assertIsNone(answer_literal('What readout speeds did the ALFOSC CCD99 controller report provide?',[item]))
        rules={'focusedReference':True,'citationId':'D-aaaaaaaaaaaaaaaa-C1','content':'- Proposals can initially apply for a maximum of 5 years,\n  but might be extended after evaluation.\n- Another rule.'}
        result=answer_literal('What is the initial maximum duration of a "Large Proposal"?',[rules])
        self.assertIn('5 years',result.validation.answer)
        self.assertIn('extended after evaluation',result.validation.answer)
        self.assertNotIn('Another rule',result.validation.answer)
        incomplete_rule={**rules,'content':'- Proposals initially apply for a maximum of 5 years, but they might be extended\n\n| (after evaluation). |'}
        result=answer_literal('What is the initial maximum duration of a Large Proposal?',[incomplete_rule])
        self.assertIn('maximum of 5 years.',result.validation.answer)
        self.assertNotIn('but they might be extended',result.validation.answer)
        self.assertIn('initial duration only',result.validation.answer)
    def test_scoped_reference_lookup_reads_values_not_answer_constants(self):
        chunks=[{'fileName':'arbitrary-report.md','title':'Correcting second-order contamination',
                 'instrument':'ALFOSC','canonicalLocation':'https://www.not.iac.es/instruments/alfosc/paper.pdf',
                 'text':'An ALFOSC second-order contamination report.'}]
        query='What is the plate scale for ALFOSC in the 2nd-order contamination report?'
        self.assertEqual(focused_sources(query,chunks),['arbitrary-report.md'])
        self.assertTrue(property_match(query,'The separation is 2 pixels (1 pixel = 0.17 arcsec).'))
        self.assertFalse(property_match(query,'16 bits per data pixel.'))
        item={'focusedReference':True,'citationId':'D-aaaaaaaaaaaaaaaa-C1','content':'The separation is 2 pixels (1 pixel = 0.17 arcsec).'}
        result=answer_literal(query,[item])
        self.assertIn('1 pixel = 0.17 arcsec',result.validation.answer)
        self.assertIn('not a current detector specification',result.validation.answer)
        self.assertIsNone(answer_literal(query+' for CCD99',[item]))
        self.assertEqual(focused_sources('What should I do with an instrument fault?', chunks),[])
        rules={'fileName':'arbitrary-rules.md','title':'Large Observing Proposals','text':'Rules for large observing proposals.'}
        self.assertEqual(focused_sources('What is the initial maximum duration of a Large Observing Proposal?', [rules]), ['arbitrary-rules.md'])
    def test_unnamed_new_controller_needs_a_subject_not_an_invented_instrument(self):
        self.assertEqual(resolve_retrieval_context('Can you list the 4 readout speeds for the new detector controller?', []).resolution,'unresolved')
        self.assertEqual(resolve_retrieval_context('Can you list the 4 readout speeds for the new detector controller?', [{'role':'user','content':'Tell me about ALFOSC.'}]).resolution,'inherited')
    def test_total_telescope_weight_is_not_a_cassegrain_instrument_limit(self):
        evidence,_=prepare_evidence([{'documentId':'a'*64,'chunkIndex':0,'text':'The total moving weight of the telescope is 43 tons.'}])
        raw=json.dumps({'claims':[{'text':evidence[0]['content'],'evidence':[{'citationId':'S1','quote':evidence[0]['content']}]}]})
        result=validate_and_render(raw,evidence,question='What is the maximum instrument weight allowed at Cassegrain?',semantic_check=lambda *args:True)
        self.assertTrue(result.abstained)
        self.assertIn('wrong_measurement_subject',result.rejection_reasons)

    def test_pixel_scale_joins_pdf_lines_and_returns_a_complete_sentence(self):
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','instrument':'POLCOR','status':'active',
              'sourceRole':'current_reference','content':'The relay optics has a 1:1 imaging which results in a pixel scale\nof 0.13 arcsec/pixel. Only shift-and-add typically improves\nthe seeing.'}
        result=answer_literal('What is the pixel scale of PolCor?',[item])
        self.assertIn('The relay optics',result.validation.answer)
        self.assertIn('0.13 arcsec/pixel.',result.validation.answer)
        self.assertNotIn('shift-and-add',result.validation.answer)

    def test_historical_matrix_value_binds_product_gain_and_amplifier(self):
        chunks=[{'documentId':'a'*64,'chunkIndex':1,'headingPath':['ALFOSC E2V CCD42-40 report','Read-out noise'],
                 'instrument':'ALFOSC','status':'historical','sourceRole':'historical_section','text':
                 '| Gain mode | Amplifier A RON | Amplifier B RON |\n| --- | --- | --- |\n| High gain | 3.11 ± 0.04 e− | 3.75 e− |\n| Low gain | 3.7 e− | 4.2 e− |'}]
        evidence,_=prepare_evidence(chunks)
        result=answer_component_table('What Amplifier A RON was measured for the ALFOSC E2V CCD42-40 in high-gain mode?',evidence)
        self.assertIn('3.11 ± 0.04',result.validation.answer)
        self.assertIn('Historical',result.validation.answer)
        self.assertNotIn('3.75',result.validation.answer)
        self.assertIsNone(answer_component_table('What Amplifier A RON was measured for the ALFOSC E2V CCD99-99 in high-gain mode?',evidence))
    def test_reference_fallback_copies_only_tightly_matched_source_values(self):
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','status':'reference_only','sourceRole':'design_reference',
              'instrument':'ALFOSC','title':'ALFOSC controller report','content':
              'From analysis of the data, the fundamental frequency of the pick-up noise is 12.34 kHz.'}
        answer=answer_excerpt('What is the fundamental frequency of pick-up noise observed with the ALFOSC controller?', [item])
        self.assertIn('12.34',answer.validation.answer)
        self.assertIn('not current operating guidance',answer.validation.answer)
        self.assertIsNone(answer_excerpt('What is the weight of ALFOSC in grams?',[item]))
        self.assertIsNone(answer_excerpt('How should I fix a fault with the ALFOSC controller?',[item]))
    def test_missing_h1_and_skipped_levels_do_not_nest_sibling_commands(self):
        blocks=markdown_blocks('## alfosc\n\n### abort\n\nStop.\n\n### resetxy\n\nReset.\n\n#### Flags\n\nOptions.\n\n### expose\n\nExpose.')
        self.assertEqual(next(b.heading_path for b in blocks if b.text=='Reset.'),['alfosc','resetxy'])
        self.assertEqual(next(b.heading_path for b in blocks if b.text=='Options.'),['alfosc','resetxy','Flags'])
        self.assertEqual(next(b.heading_path for b in blocks if b.text=='Expose.'),['alfosc','expose'])
    def test_current_command_reference_is_not_misclassified_as_a_design_paper(self):
        current=annotate_source({'canonicalLocation':'https://www.not.iac.es/instruments/development/CCD-controller/current/CCD-commands.pdf'})
        self.assertEqual(current['sourceRole'],'command_reference')
        aggregate=annotate_source({'category':'sequencer_reference','headingPath':['Sequencer Command Reference','alfosc','resetxy']})
        self.assertEqual(aggregate['instrument'],'ALFOSC')
        self.assertEqual(aggregate['sourceRole'],'command_reference')
        for category in ('development','detectors','FITS-header'):
            source=annotate_source({'canonicalLocation':f'https://www.not.iac.es/instruments/{category}/'})
            self.assertNotEqual(source['sourceRole'],'instrument_landing')

    def test_named_command_definition_uses_the_actual_reference_entry(self):
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','status':'active','sourceRole':'command_reference','instrument':'ALFOSC',
              'section':'`resetxy`','content':'### `resetxy`\n\nResets binning to 1 and X/Y sizes to maximum.\n\n- **Arguments:** `[-d]`'}
        result=answer_literal('What does the ALFOSC resetxy command do?',[item])
        self.assertIn('binning to 1',result.validation.answer)
        self.assertNotIn('Arguments',result.validation.answer)
        self.assertIsNone(answer_literal('What does the NOTCAM resetxy command do?',[item]))

    def test_property_lookup_must_bind_the_requested_detector(self):
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','status':'active','sourceRole':'reference',
              'title':'Another detector','content':'| Pixel size | 15µm |'}
        self.assertIsNone(answer_literal('What is the physical pixel size of SITe SI-003A CCD?',[item]))

    def test_instrument_settings_bind_named_columns_and_instrument_row(self):
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','status':'active','sourceRole':'operator_guide',
              'content':'| instrument | foc-pos | tv-foc |\n| --- | --- | --- |\n| ALFOSC | 25555 | 499 |\n| NOTCAM | 23333 | 300 |'}
        result=answer_component_table('What is the default foc-pos and tv-foc for ALFOSC?',[item])
        self.assertIn('25555',result.validation.answer)
        self.assertIn('499',result.validation.answer)
        self.assertNotIn('23333',result.validation.answer)

    def test_unconnected_autoguiding_controls_are_not_an_internal_program_sequence(self):
        evidence,_=prepare_evidence([{'documentId':'a'*64,'chunkIndex':0,'text':'The AG off button turns autoguiding off.'},
                                     {'documentId':'b'*64,'chunkIndex':0,'text':'teloffset offsets the telescope.'}])
        raw=json.dumps({'claims':[{'text':e['content'],'evidence':[{'citationId':e['sourceRef'],'quote':e['content']}]} for e in evidence]})
        result=validate_and_render(raw,evidence,question='Explain the sequence when the teloffset program runs while autoguided.',semantic_check=lambda *args:True)
        self.assertTrue(result.abstained)
        self.assertIn('unsupported_complete_procedure',result.rejection_reasons)

    def test_capability_prose_and_data_policy_are_complete_source_excerpts(self):
        item={'citationId':'D-aaaaaaaaaaaaaaaa-C1','instrument':'ALFOSC','status':'active',
              'sourceRole':'instrument_landing','content':'ALFOSC has imaging mode and can also be used for spectroscopy and polarimetry.'}
        result=answer_literal('What is ALFOSC used for?',[item])
        self.assertIn('polarimetry',result.validation.answer)
        policy={**item,'sourceRole':'operator_guide','content':'Only principal investigators have direct data access. They can grant access by distributing a shared link.'}
        result=answer_procedure('Can the team access data, or must the PI share it?',[policy])
        self.assertIn('shared link',result.validation.answer)

    def test_related_background_does_not_answer_a_requested_duration(self):
        evidence,_=prepare_evidence([{'documentId':'a'*64,'chunkIndex':0,'text':'Large observing proposals can be submitted every semester.'}])
        raw=json.dumps({'claims':[{'text':evidence[0]['content'],'evidence':[{'citationId':'S1','quote':evidence[0]['content']}]}]})
        result=validate_and_render(raw,evidence,question='What is the maximum duration for a Large Observing Proposal?',semantic_check=lambda *args:True)
        self.assertTrue(result.abstained)
        self.assertIn('requested_value_not_answered',result.rejection_reasons)

    def test_signed_catalogue_coordinates_are_not_phone_numbers(self):
        line='[TCS] append-object my_star 12 12 12 +12 12 12 2000 0.1 -0.1 12'
        self.assertEqual(scrub_sensitive_text(line),line)
        self.assertIn('[phone removed]',scrub_sensitive_text('Contact: +34 922 123 456'))

    def test_unicode_minus_and_pdf_degree_notation_are_equivalent_not_sign_changes(self):
        evidence,_=prepare_evidence([{'documentId':'a'*64,'chunkIndex':0,'text':'The detector temperature is −120 ◦ C.'}])
        def result(number):
            return validate_and_render(json.dumps({'claims':[{'text':f'The detector temperature is {number}°C.',
                                       'evidence':[{'citationId':'S1','quote':evidence[0]['content']}]}]}),evidence,
                                       semantic_check=lambda *args:True)
        self.assertFalse(result('-120').abstained)
        self.assertTrue(result('120').abstained)

    def test_a_true_but_unrelated_fact_cannot_answer_a_corpus_gap(self):
        evidence,_=prepare_evidence([{'documentId':'a'*64,'chunkIndex':0,'text':'The baffle lamp status is on the TCS display.'}])
        raw=json.dumps({'claims':[{'text':'The baffle lamp status is on the TCS display.',
                                 'evidence':[{'citationId':'S1','quote':evidence[0]['content']}]}]})
        result=validate_and_render(raw,evidence,question='How do I recalibrate the NOT quantum teleporter?',
                                   semantic_check=lambda *args:True)
        self.assertTrue(result.abstained)
        self.assertIn('unrelated_to_question',result.rejection_reasons)

    def test_component_lookup_preserves_column_units_and_uses_source_values(self):
        evidence=[{'citationId':'D-aaaaaaaaaaaaaaaa-C2','instrument':'ALFOSC','sourceRole':'current_reference',
                   'status':'active','content':'| Grism | central | dispersion |\n| --- | --- | --- |\n'
                   '| Grism | [Å] | [Å/pixel] |\n| 18 | 4555 | 0.77 |\n| 19 | 5500 | 1.5 |'}]
        answer=answer_component_table('What are the central wavelength and dispersion of G#18?',evidence)
        self.assertIn('4555 [Å]',answer.validation.answer)
        self.assertIn('0.77 [Å/pixel]',answer.validation.answer)
        self.assertNotIn('5500',answer.validation.answer)
        self.assertIsNone(answer_component_table('What are the central wavelength and dispersion of G#20?',evidence))
        evidence[0]['sourceRole']='design_reference'
        self.assertIsNone(answer_component_table('What are the central wavelength and dispersion of G#18?',evidence))

    def test_indexed_reference_expansion_is_bounded_and_official_only(self):
        chunks=[{'canonicalLocation':'https://www.not.iac.es/instruments/test/',
                 'text':'[second-order contamination report](report.pdf) '
                        '[second-order contamination evil](https://evil.test/steal.pdf) '
                        '[second-order contamination exec](javascript:alert)'}]
        result=matching_reference_links('What is the second-order contamination threshold?',chunks)
        self.assertEqual(result,[('instruments-test-report-pdf.md','https://www.not.iac.es/instruments/test/report.pdf')])
        self.assertEqual(canonical_key('http://not.iac.es/instruments/test/report.pdf#page2'),canonical_key(result[0][1]))
        self.assertIsNone(canonical_key('https://not.iac.es.evil.test/'))

    def test_control_instruction_is_not_cut_or_confused_with_other_actions(self):
        chunks=[{'documentId':'d'*64,'chunkIndex':0,'section':'Startup','headingPath':['Startup'],
                 'previousSection':'','nextSection':'Startup','status':'active','sourceRole':'operator_guide',
                 'authority':'tier_1_authoritative','text':'4. To abort a NOTCam script, type Ctrl-C and wait for the exposure to finish.\n5. An unrelated operation.'}]
        evidence,_=prepare_evidence(chunks)
        answer=answer_procedure('How should I interrupt a NOTCam exposure or script?',evidence)
        self.assertIn('wait for the exposure to finish',answer.validation.answer)
        self.assertNotIn('unrelated',answer.validation.answer)
        chunks[0]['text']='4. To abort a NOTCam script, type Ctrl-C and wait'
        evidence,_=prepare_evidence(chunks)
        self.assertIsNone(answer_procedure('How should I interrupt a NOTCam exposure or script?',evidence))

    def test_a_named_command_is_not_an_answer_to_missing_internal_sequence(self):
        chunks=[{'documentId':'e'*64,'chunkIndex':0,'section':'Teloffset','headingPath':['Teloffset'],
                 'previousSection':'','nextSection':'Other','status':'active','sourceRole':'operator_guide',
                 'authority':'tier_1_authoritative','text':'Use telescope.teloffset to offset the telescope.'}]
        evidence,_=prepare_evidence(chunks)
        self.assertIsNone(answer_procedure('Explain the sequence of events when teloffset runs while the telescope is already being autoguided.',evidence))

    def test_procedure_requires_complete_provenance_and_preserves_last_steps(self):
        source = {'documentId':'a'*64,'fileName':'guide.md','status':'active',
                  'authority':'tier_1_authoritative','sourceRole':'operator_guide',
                  'section':'Align objects','headingPath':['Align objects']}
        chunks=[{**source,'chunkIndex':0,'previousSection':'','nextSection':'Align objects',
                 'text':'Use **slitrot**.\n\n1. Take an exposure.\n2. Mark both targets.'},
                {**source,'chunkIndex':1,'previousSection':'Align objects','nextSection':'Other',
                 'text':'3. Rotate the field.\n4. Place objects onto the slit.\n\nOther notes.'}]
        evidence,_=prepare_evidence(chunks)
        result=answer_procedure('How do I align objects using slitrot?',evidence)
        self.assertIn('4. Place objects onto the slit.',result.validation.answer)
        self.assertNotIn('Other notes',result.validation.answer)
        self.assertIsNone(answer_procedure('How do I align objects using slitrot?',evidence[:1]))
        unknown,_=prepare_evidence([{k:v for k,v in chunks[0].items() if k!='nextSection'}])
        self.assertIsNone(answer_procedure('How do I align objects using slitrot?',unknown))
        truncated,_=prepare_evidence(chunks,max_content_chars=20)
        self.assertIsNone(answer_procedure('How do I align objects using slitrot?',truncated))
        self.assertIsNone(answer_procedure('How do I bypass slitrot interlocks?',evidence))

    def test_named_calibration_recipe_copies_commands_not_an_invented_series(self):
        chunks=[{'documentId':'b'*64,'chunkIndex':3,'section':'Darks','headingPath':['Darks'],
                 'previousSection':'Calibration','nextSection':'Flats','status':'active',
                 'authority':'tier_1_authoritative','sourceRole':'operator_guide',
                 'text':'Use notcam.dark(t) for one dark. Use notcam.mdark(t,N) for N darks. Discard the first.'}]
        evidence,_=prepare_evidence(chunks)
        result=answer_procedure('How should I take NOTCam dark frames?',evidence)
        self.assertIn('notcam.dark(t) for one dark',result.validation.answer)
        self.assertIn('Discard the first',result.validation.answer)
        self.assertIsNone(answer_procedure('How should I take NOTCam flat frames?',evidence))

    def test_data_guide_preserves_policy_and_download_instructions(self):
        source={'documentId':'c'*64,'status':'active','sourceRole':'operator_guide',
                'authority':'tier_1_authoritative'}
        chunks=[{**source,'chunkIndex':1,'section':'NOT data server','headingPath':['NOT data server'],
                 'previousSection':'Intro','nextSection':'How to get my data?',
                 'text':'Only principal investigators have direct access. Use the same proposal email.'},
                {**source,'chunkIndex':2,'section':'How to get my data?','headingPath':['How to get my data?'],
                 'previousSection':'NOT data server','nextSection':'Share',
                 'text':'2. Log in.\n3. Open File Station.\n4. Download the selected files.'}]
        evidence,_=prepare_evidence(chunks)
        result=answer_procedure('How can I download my observing data?',evidence)
        self.assertIn('Only principal investigators',result.validation.answer)
        self.assertIn('4. Download',result.validation.answer)

    def test_literal_values_and_weather_rules_are_not_hardcoded(self):
        item = {"citationId":"D-aaaaaaaaaaaaaaaa-C0", "instrument":"NOTCAM", "status":"active",
                "sourceRole":"current_reference", "source":"test", "content":
                "NOTCam is a near-infrared instrument.\n\nNOTCam is capable of:\n- Wide field imaging (0.222\"/pixel)\n- Spectroscopy (R=2300)\n"}
        self.assertIn("near-infrared", answer_literal("What is NOTCAM?", [item]).validation.answer)
        self.assertIn("Spectroscopy", answer_literal("What is NOTCAM used for?", [item]).validation.answer)
        self.assertIn("0.222", answer_literal("What is the wide-field pixel scale of NOTCAM?", [item]).validation.answer)
        weather = {**item,"instrument":"", "sourceRole":"operator_guide", "content":
                   "| Humidity | >88% | Close telescope; After 15 min below 88%, reopen |"}
        answer = answer_operational("What must I do in high humidity?",[weather]).validation.answer
        self.assertIn(">88%",answer)
        self.assertIn("After 15 min below 88%",answer)
        bypass = answer_operational("Can I bypass a safety interlock in high humidity?",[weather]).validation.answer
        self.assertTrue(bypass.startswith("No."))
        self.assertNotIn("reset",bypass)
        transposed = {**weather, "content":"| Humidity | Wind |\n| --- | --- |\n| >88% - Close telescope; After 15 min below 88%, reopen | 20 m/s - Close telescope |"}
        self.assertIn("After 15 min below 88%",answer_operational("What do I do in high humidity?",[transposed]).validation.answer)

    def test_semantic_check_cannot_override_measurements_or_provenance(self):
        evidence,_ = prepare_evidence([{"documentId":"a"*64,"chunkIndex":0,
                                       "text":"A device has a diameter of 1.8 arcsec.","status":"active"}])
        def validate(statement,checker):
            return validate_and_render(json.dumps({"claims":[{"text":statement,"evidence":[
                {"citationId":evidence[0]["citationId"],"quote":evidence[0]["content"]}]}]}),
                evidence,semantic_check=checker)
        self.assertTrue(validate("The device has a diameter of 1.8 arcminutes.", lambda *args: True).abstained)
        self.assertTrue(validate("The device has a diameter of 2.8 arcsec.", lambda *args: True).abstained)
        self.assertTrue(validate("A device has a diameter of 1.8 arcsec.", lambda *args: False).abstained)

    def test_source_alias_is_resolved_to_actual_stable_citation(self):
        evidence,_=prepare_evidence([{"documentId":"a"*64,"chunkIndex":4,"text":"The instrument images in infrared."}])
        raw=json.dumps({"claims":[{"text":"The instrument images in infrared.","evidence":[{"citationId":"S1","quote":"The instrument images in infrared."}]}]})
        result=validate_and_render(raw,evidence)
        self.assertIn("[D-aaaaaaaaaaaaaaaa-C4]", result.answer)
        self.assertNotIn("[S1]", result.answer)
        self.assertTrue(validate_and_render(raw.replace('S1','S99'), evidence).abstained)

    def test_miscopied_excerpt_requires_independent_source_entailment(self):
        evidence,_=prepare_evidence([{"documentId":"a"*64,"chunkIndex":0,"text":"The device images in infrared."}])
        raw=json.dumps({"claims":[{"text":"The device images in infrared.","evidence":[{"citationId":"S1","quote":"A miscopied invented excerpt."}]}]})
        self.assertTrue(validate_and_render(raw,evidence).abstained)
        self.assertTrue(validate_and_render(raw,evidence,semantic_check=lambda *args:None).abstained)
        self.assertTrue(validate_and_render(raw,evidence,semantic_check=lambda *args:False).abstained)
        def verified(statement,quotes,*args):
            self.assertEqual(quotes,["The device images in infrared."])
            return True
        result=validate_and_render(raw,evidence,semantic_check=verified)
        self.assertFalse(result.abstained)
        self.assertEqual(result.resolved_excerpts,1)

    def test_merged_weather_cells_and_instruction_boundaries(self):
        html = '''<table><tr><th>Condition</th><th>Limit</th><th>Action</th></tr>
        <tr><td rowspan=2>Humidity</td><td>&gt;90%</td><td>Close telescope<br><br>After 20 min below 90%, reopen</td></tr>
        <tr><td>Ice</td><td>Keep closed</td></tr>
        <tr><td rowspan=2>Wind</td><td>15 m/s</td><td>Avoid wind direction</td></tr>
        <tr><td>20 m/s</td><td>Close telescope</td></tr></table>'''
        text = html_to_markdown(html)
        self.assertIn("| Humidity | >90% | Close telescope; After 20 min below 90%, reopen |", text)
        self.assertIn("| Humidity | Ice | Keep closed |", text)
        self.assertIn("| Wind | 20 m/s | Close telescope |", text)

    def test_natural_component_followups_and_topic_switches(self):
        history = [{"role":"user", "content":"what is FIES?"}]
        for query in ("how many fivers are available?", "what resolution do the different fibres offer?",
                      "And the diameter on sky for fibre number 4?", "How are the fibers connected to the telescope?"):
            context = resolve_retrieval_context(query, history)
            self.assertEqual(context.resolution, "inherited")
            self.assertIn("FIES", context.query)
        for query in ("What is NOTCAM?", "What is the telescope plate scale?", "When is the road closed?"):
            self.assertNotEqual(resolve_retrieval_context(query, history).resolution, "inherited")
        history += [{"role":"user", "content":"Compare FIES and NOTCAM"}]
        self.assertEqual(resolve_retrieval_context("What does it cover?", history).resolution, "ambiguous")

    def test_subject_clarification_preserves_the_actual_question(self):
        history = [{"role":"user","content":"what is FIES?"},
                   {"role":"user","content":"how many fivers are available?"}]
        context = resolve_retrieval_context("i mean fibers on FIES", history)
        self.assertEqual(context.resolution, "clarified")
        self.assertIn("how many fibers", context.query)
        self.assertIn("FIES", context.query)
        self.assertNotEqual(resolve_retrieval_context("i mean FIES, what is the aperture?", history).resolution, "clarified")

    def test_layout_removed_data_preserved_and_spare_scope_separated(self):
        html = '''<title>Nordic Optical Telescope</title><table><tr><td><h2>Instrument guide</h2>
        <table><tr><th colspan=3>Default bundle</th></tr><tr><th>fibre<th>resolution<th>diameter</tr>
        <tr><td>#1 low-res<td>25000<td>2.5 arcsec<tr><td>#4 high-res<td>65000<td>1.3 arcsec</table>
        <b>Spare bundle: old</b><br><p>Historical configuration only.</table>'''
        text = html_to_markdown(html)
        self.assertEqual(meaningful_title(html), "Instrument guide")
        self.assertIn("| fiber #4 high-res | 65000 | 1.3 arcsec |", text)
        chunks = structured_chunks(text, target_chars=900)
        current = next(c for c in chunks if "fiber #4" in c.text)
        self.assertNotIn("Historical configuration", current.text)
        self.assertTrue(current.metadata["completeTables"])
        spare = next(c for c in chunks if "Historical configuration" in c.text)
        self.assertEqual(annotate_source(spare.metadata)["sourceRole"], "historical_section")

    def test_prose_layout_does_not_become_a_giant_table_cell(self):
        prose = "This is instrument reference prose. " * 40
        html = f'<table><tr><td></td><td>{prose}<table><tr><th>Mode</th><th>Value</th></tr><tr><td>A</td><td>2</td></tr></table></td></tr></table>'
        text = html_to_markdown(html)
        self.assertNotIn("NOTBOTDATATABLE", text)
        self.assertNotIn("Column 2",text)
        self.assertIn("| A | 2 |", text)

    def test_split_table_is_not_a_complete_inventory(self):
        table = "| fibre | mode | diameter |\n| --- | --- | --- |\n" + "\n".join(
            f"| fiber #{i} high-res | {'text '*25} | 1.3 arcsec |" for i in range(1,60))
        chunks = structured_chunks(table, target_chars=450)
        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(not c.metadata["completeTables"] for c in chunks))
        self.assertTrue(all("| fibre | mode | diameter |" in c.text for c in chunks))

    def test_small_technical_tables_and_keyboard_paragraphs_are_not_split(self):
        table='| Grism | central | dispersion |\n| --- | --- | --- |\n| Grism | [Å] | [Å/pixel] |\n'+ '\n'.join(f'| {i} | 4555 | 0.77 |' for i in range(1,30))
        chunks=structured_chunks(table,target_chars=450)
        self.assertEqual(len(chunks),1)
        self.assertEqual(chunks[0].metadata['completeTables'],[table])
        paragraph='Identify the target by pressing a+q. '+ 'Confirm the image before continuing. '*30
        chunks=structured_chunks(paragraph,target_chars=450)
        self.assertEqual(len(chunks),1)
        self.assertNotIn('fragment',chunks[0].metadata['contentTypes'])
        evidence,_=prepare_evidence([{**chunks[0].metadata,'text':chunks[0].text,'documentId':'a'*64,
                                    'status':'active','sourceRole':'operator_guide'}])
        answer=answer_procedure('How do I identify the target? ',evidence)
        self.assertIn(paragraph.strip(),answer.validation.answer)

    def test_identifiers_units_row_binding_and_count_derivations(self):
        table = "| fiber | mode | resolution | aperture |\n| --- | --- | --- | --- |\n" + "\n".join([
            "| fiber 1 | low-res | R=25000 | 2.5 arcsec |",
            "| fiber 2 | med-res | R=45000 | 1.3 arcsec |",
            "| fiber 3 | med-res | R=45000 | 1.3 arcsec |",
            "| fiber 4 | high-res | R=65000 | 1.3 arcsec |",
            "| fiber 5 | high-res | R=65000 | calibration fiber for simultaneous-ThAr |"])
        evidence, _ = prepare_evidence([{"documentId":"a"*64,"chunkIndex":0,"instrument":"FIES",
            "section":"Choose the science fibers", "status":"active", "authority":"tier_1_authoritative",
            "text":table,"completeTables":[table]}])
        cid = evidence[0]["citationId"]
        def validate(statement, quote=table):
            return validate_and_render(json.dumps({"claims":[{"text":statement,"evidence":[{"citationId":cid,"quote":quote}]}]}), evidence)
        self.assertFalse(validate("FIES high-resolution fibre (#4) has a diameter of 1.3 arcseconds.").abstained)
        self.assertFalse(validate("FIES fiber 4 offers R=65,000.").abstained)
        self.assertFalse(validate("FIES has four science fibers.").abstained)
        self.assertTrue(validate("FIES fiber 4 has a diameter of 2.5 arcsec.").abstained)
        self.assertTrue(validate("FIES fiber 99 has a diameter of 1.3 arcsec.").abstained)
        self.assertTrue(validate("FIES fiber 4 has a diameter of 1.3 arcminutes.").abstained)
        self.assertTrue(validate("FIES has six science fibers.").abstained)
        self.assertTrue(validate("FIES has five science fibers.").abstained)

    def test_design_sources_cannot_be_current_operating_configuration(self):
        chunk = annotate_source({"canonicalLocation":"https://www.not.iac.es/instruments/fies/bundleD/design.pdf",
                                "status":"active","authority":"tier_2_reference"})
        self.assertEqual(chunk["status"], "reference_only")

    def test_cookbook_query_url_instrument_and_spare_captions(self):
        source = annotate_source({"canonicalLocation":"https://www.not.iac.es/observing/cookbook/current/Cookbook.php?instrument=NOTCam", "instrument":"[missing]"})
        self.assertEqual(source["instrument"], "NOTCAM")
        self.assertEqual(source["sourceRole"], "operator_guide")
        for caption in ("Fibre bundle C (spare)", "Spare bundle: bundle C", "Outdated results for bundle C"):
            self.assertEqual(annotate_source({"headingPath":[caption]})["status"], "historical")

    def test_generic_lookup_uses_supplied_values_not_constants(self):
        table = "| fiber | mode | resolution | aperture |\n| --- | --- | --- | --- |\n" + "\n".join([
            "| fiber 1 | low-res | R=21000 | 2.9 arcsec |",
            "| fiber 4 | high-res | R=78000 | 1.7 arcsec |",
            "| fiber 5 | high-res | R=78000 | calibration fiber |"])
        chunk = annotate_source({"documentId":"a"*64,"chunkIndex":0,"instrument":"FIES", "status":"active",
                                 "canonicalLocation":"https://www.not.iac.es/observing/cookbook/current/Cookbook.php?instrument=FIES",
                                 "text":table,"completeTables":[table]})
        evidence,_ = prepare_evidence([chunk])
        count = answer_reference("How many fibers on FIES?", evidence)
        self.assertIn("2 science fibers", count.validation.answer)
        aperture = answer_reference("What diameter on sky for FIES fiber #4?", evidence)
        self.assertIn("1.7 arcsec", aperture.validation.answer)
        self.assertNotIn("1.3 arcsec", aperture.validation.answer)
        self.assertTrue(answer_reference("What diameter for FIES fiber #99?", evidence).validation.abstained)
        self.assertIsNone(answer_reference("Can FIES fiber #4 observe at 500nm?", evidence))
        self.assertIsNone(answer_reference("Why is FIES fiber #4 broken?", evidence))
        self.assertIsNone(answer_reference("How many historical FIES fibers?", evidence))
        incomplete,_ = prepare_evidence([{**chunk,"completeTables":[]}])
        self.assertIsNone(answer_reference("How many fibers on FIES?", incomplete))


if __name__ == "__main__":
    unittest.main()
