"""Artificial research-engine fixtures; no external corpus or Pilot training."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import pickle
import tempfile
import unittest
from unittest.mock import patch

PATH=Path(__file__).resolve().parents[1]/'research_log/run_usage_model_study_20261031.py'
SPEC=importlib.util.spec_from_file_location('candidate_study',PATH)
m=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(m)


class FakeModel:
    def __init__(self,choice='bz2',events=None):self.choice=choice;self.events=events if events is not None else []
    def predict(self,frame):
        self.events.append('predict')
        if list(frame.columns)!=list(m.FEATURE_NAMES):raise ValueError('feature contract')
        return [self.choice]


def trials():
    return [dict(sample_id='fixture',strategy='fixture',repeat_index=i,algorithm='zstd',package_bytes=12,
                 payload_sha256='synthetic',verified=True,compression_ns=i*1000,restoration_ns=i*2000,
                 feature_ns=0,prediction_ns=0) for i in range(1,6)]


class StudyTests(unittest.TestCase):
    def workspace_temp(self):
        path=m.ROOT/'data/temp';path.mkdir(parents=True,exist_ok=True)
        return tempfile.TemporaryDirectory(prefix='usage_study_fixture_',dir=path)

    def test_metrics_keep_four_classes_and_absent_class_penalty(self):
        result=m.classification(['zstd','zstd'],['zstd','zstd'])
        self.assertEqual(result['accuracy'],1)
        self.assertEqual(result['macro_f1'],.25)
        self.assertEqual(len(result['confusion_matrix']),4)

    def test_primary_comparison_weights_groups_equally(self):
        rows=[]
        for group,diffs in (('a',[1,1,1]),('b',[-3])):
            for diff in diffs:
                rows.append(dict(origin_group_id=group,true_algorithm='zstd',chosen_algorithm='zstd',
                    zstd_cost=10,policy_cost=10,regret=0,difference_vs_majority=diff,
                    compressed_size=5,compression_time_ms=1,decompression_time_ms=1))
        result=m.summarize_choices(rows)
        self.assertEqual(result['primary_group_mean_difference_vs_majority'],-1)

    def test_feature_frame_accepts_only_precompression_schema(self):
        values={f:1 for f in m.FEATURE_NAMES}
        self.assertEqual(list(m.feature_frame(values).columns),list(m.FEATURE_NAMES))
        for extra in ('score','format','measured_compression_ms'):
            with self.assertRaises(ValueError):m.feature_frame({**values,extra:1})
        values[m.FEATURE_NAMES[0]]=float('nan')
        with self.assertRaises(ValueError):m.feature_frame(values)

    def test_repeat_median_is_computed_from_all_raw_slots(self):
        value=m.aggregate_trials(trials())[('fixture','fixture')]
        self.assertEqual(value['compression_ns'],.003)
        self.assertEqual(value['restoration_ns'],.006)

    def test_incomplete_duplicate_nonpositive_or_inconsistent_trials_reject(self):
        invalid=[trials()[:4]]
        for field,value in (('repeat_index',2),('algorithm','gzip'),('package_bytes',99),
                            ('verified',False),('compression_ns',0),('feature_ns',-1)):
            rows=trials();rows[0][field]=value;invalid.append(rows)
        for rows in invalid:
            with self.subTest(rows=rows):
                with self.assertRaises(ValueError):m.aggregate_trials(rows)

    def test_pipeline_predicts_before_exactly_one_codec_and_preserves_source(self):
        with self.workspace_temp() as folder:
            root=Path(folder);source=root/'input_한글 &.txt';data=b'ABC123'*100;source.write_bytes(data)
            events=[];original=m.compress_data
            def compress(value,algorithm):
                events.append('compress_'+algorithm);return original(value,algorithm)
            with patch.object(m,'compress_data',side_effect=compress) as call:
                result=m.execute_pipeline(source,root/'trial',hashlib.sha256(data).hexdigest(),model=FakeModel(events=events),expected_algorithm='bz2')
            self.assertEqual(events,['predict','compress_bz2']);self.assertEqual(call.call_count,1)
            self.assertEqual(source.read_bytes(),data)
            self.assertEqual((m.ROOT/result['restored_relative_path']).read_bytes(),data)
            self.assertEqual(result['algorithm'],'bz2')
            self.assertGreater(result['feature_ns'],0)

    def test_fixed_zstd_does_not_extract_features_or_predict(self):
        with self.workspace_temp() as folder:
            root=Path(folder);source=root/'input';source.write_bytes(b'abc'*100)
            with patch.object(m,'extract_features',side_effect=AssertionError('must not be called')):
                result=m.execute_pipeline(source,root/'trial',m.sha(source))
            self.assertEqual(result['algorithm'],'zstd');self.assertEqual(result['feature_ns'],0)

    def test_hash_or_prediction_drift_rejects_before_compression(self):
        with self.workspace_temp() as folder:
            root=Path(folder);source=root/'input';source.write_bytes(b'abc'*100)
            with patch.object(m,'compress_data',side_effect=AssertionError('must not compress')):
                with self.assertRaises(ValueError):m.execute_pipeline(source,root/'bad_hash','0'*64,model=FakeModel())
                with self.assertRaises(ValueError):m.execute_pipeline(source,root/'bad_choice',m.sha(source),model=FakeModel(),expected_algorithm='gzip')

    def test_restoration_failure_is_not_saved_as_success(self):
        with self.workspace_temp() as folder:
            root=Path(folder);source=root/'input';source.write_bytes(b'abc'*100)
            original=m.decompress_data;calls=[]
            def decompress(payload,algorithm):
                calls.append(algorithm);return original(payload,algorithm) if len(calls)==1 else b'wrong'
            with patch.object(m,'decompress_data',side_effect=decompress):
                with self.assertRaises(ValueError):m.execute_pipeline(source,root/'trial',m.sha(source))
            self.assertFalse((root/'trial/restored/input').exists())

    def test_existing_pipeline_output_is_not_overwritten(self):
        with self.workspace_temp() as folder:
            root=Path(folder);source=root/'input';source.write_bytes(b'abc'*100);(root/'trial').mkdir()
            with self.assertRaises(FileExistsError):m.execute_pipeline(source,root/'trial',m.sha(source))

    def test_trusted_model_metadata_and_hash_are_checked(self):
        with self.workspace_temp() as folder:
            root=Path(folder);config=json.loads((m.ROOT/'config/experiment_config.json').read_bytes())
            config['random_forest']['n_estimators']=2
            X=m.pd.DataFrame([[0]*len(m.FEATURE_NAMES),[1]*len(m.FEATURE_NAMES)],columns=list(m.FEATURE_NAMES))
            for kind,fit in (('decision_tree',m.fit_decision_tree),('random_forest',m.fit_random_forest)):
                model=fit(X,['gzip','zstd'],config[kind]);path=root/(kind+'.pkl');path.write_bytes(pickle.dumps(model))
                item={'file':path.name,'sha256':m.sha(path),'kind':kind,'classes':model.classes_.tolist(),'parameters':model.get_params()}
                training={'feature_names':list(m.FEATURE_NAMES),'python':m.platform.python_version(),
                          'packages':{'scikit-learn':m.version('scikit-learn')}}
                with patch.object(m,'OUT',root):
                    loaded=m.load_model(item,training,config)
                    self.assertEqual(loaded.predict(X).tolist(),['gzip','zstd'])
                    with self.assertRaises(ValueError):m.load_model({**item,'sha256':'0'*64},training,config)
                    with self.assertRaises(ValueError):m.load_model({**item,'classes':['bz2']},training,config)
                    with self.assertRaises(ValueError):m.load_model(item,{**training,'python':'invalid-version'},config)
                    with self.assertRaises(ValueError):m.load_model({**item,'parameters':{**item['parameters'],'random_state':999}},training,config)


if __name__=='__main__':unittest.main()
