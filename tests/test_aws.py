"""Integração AWS: cofre de provas (S3 + Object Lock) e Claude via Amazon Bedrock — sem rede e sem credenciais reais."""
import os
os.environ['TORRE_LLM'] = '0'
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app import cloud_aws
from app.cloud_aws import EvidenceVault


class LocalVault(unittest.TestCase):
    def test_local_mode_is_immutable_and_verifiable(self):
        with tempfile.TemporaryDirectory() as d:
            v = EvidenceVault(bucket='', local_root=Path(d))
            self.assertEqual(v.mode, 'local')
            r = v.put_json('modelo', 'emergencia-v1', {'auc': 0.87})
            self.assertTrue(v.verify_local(r))
            self.assertTrue(v.has('modelo', 'emergencia-v1'))
            (Path(d) / r['key']).write_bytes(b'adulterado')
            self.assertFalse(v.verify_local(r))   # adulteração detectada pelo hash
            self.assertEqual(v.status()['by_kind'], {'modelo': 1})


try:
    import boto3
    from botocore.stub import Stubber, ANY
    HAVE_BOTO = True
except ImportError:
    HAVE_BOTO = False


@unittest.skipUnless(HAVE_BOTO, 'boto3 não instalado')
class S3Vault(unittest.TestCase):
    def test_put_uses_object_lock_compliance_kms_and_checksum(self):
        s3 = boto3.client('s3', region_name='sa-east-1', aws_access_key_id='x', aws_secret_access_key='y')
        with Stubber(s3) as stub, tempfile.TemporaryDirectory() as d:
            stub.add_response('put_object', {}, {'Bucket': 'cofre', 'Key': ANY, 'Body': ANY, 'ChecksumAlgorithm': 'SHA256',
                                                 'ObjectLockMode': 'COMPLIANCE', 'ObjectLockRetainUntilDate': ANY,
                                                 'Metadata': ANY, 'ServerSideEncryption': 'aws:kms'})
            v = EvidenceVault(client=s3, bucket='cofre', prefix='t/', retention_days=30, local_root=Path(d))
            r = v.put('snapshot-sigbm', 'sigbm-1', b'csv')
            stub.assert_no_pending_responses()
            self.assertEqual(r['mode'], 's3')
            self.assertTrue(r['key'].startswith('t/snapshot-sigbm/'))
            self.assertIn('retain_until', r)

    def test_s3_failure_keeps_local_copy(self):
        s3 = boto3.client('s3', region_name='sa-east-1', aws_access_key_id='x', aws_secret_access_key='y')
        with Stubber(s3) as stub, tempfile.TemporaryDirectory() as d:
            stub.add_client_error('put_object', 'AccessDenied')
            v = EvidenceVault(client=s3, bucket='cofre', local_root=Path(d))
            r = v.put_json('modelo', 'm', {'a': 1})
            self.assertIn('local', r['mode'])
            self.assertTrue(v.verify_local(r))
            self.assertIn('AccessDenied', v.last_error)


class BedrockProvider(unittest.TestCase):
    def test_bedrock_call_has_no_server_fallback_and_uses_configured_model(self):
        sent = {}

        class Msgs:
            def create(self, **kw):
                sent.update(kw)
                return type('R', (), {'stop_reason': 'end_turn', 'content': [type('B', (), {'type': 'text', 'text': '{"ok": true}'})()]})()

        fake = type('C', (), {'messages': Msgs()})()
        with mock.patch.dict(os.environ, {'TORRE_LLM_PROVIDER': 'bedrock', 'TORRE_BEDROCK_MODEL': 'modelo-configurado'}), \
                mock.patch.object(cloud_aws, 'make_client', return_value=fake):
            out = cloud_aws.structured_call('sys', 'user', {'type': 'object'})
        self.assertEqual(json.loads(out), {'ok': True})
        self.assertEqual(sent['model'], 'modelo-configurado')
        self.assertNotIn('fallbacks', sent)
        self.assertNotIn('betas', sent)

    def test_status_reports_provider(self):
        from app.ai import llm_status
        with mock.patch.dict(os.environ, {'TORRE_LLM_PROVIDER': 'bedrock', 'TORRE_LLM': '1'}):
            st = llm_status()
        self.assertEqual(st['provider'], 'bedrock')
        self.assertTrue(st['enabled'])  # credenciais AWS pelo mecanismo padrão; sem chave da Anthropic

    def test_bedrock_client_is_created(self):
        with mock.patch.dict(os.environ, {'TORRE_LLM_PROVIDER': 'bedrock', 'AWS_REGION': 'us-east-1',
                                          'AWS_ACCESS_KEY_ID': 'x', 'AWS_SECRET_ACCESS_KEY': 'y'}):
            c = cloud_aws.make_client()
        self.assertEqual(type(c).__name__, 'AnthropicBedrock')


if __name__ == '__main__':
    unittest.main()
