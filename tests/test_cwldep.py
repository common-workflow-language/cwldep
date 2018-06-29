from __future__ import absolute_import
import unittest
import cwldep
from mock import patch, Mock, mock_open, call


class DownloadTestCase(unittest.TestCase):
    @patch('cwldep.os')
    @patch('cwldep.logging')
    @patch('cwldep.requests')
    def test_download_check_only_not_a_file(self, mock_requests, mock_logging, mock_os):
        verified = {}
        locks = {}
        mocked_open = mock_open()
        mock_os.path.isfile.return_value = False
        mock_os.path.relpath.return_value = 'myrelpath'
        cwldep.download(tgt="myfile.cwl", url="someurl", version="1",
                        locks=locks, verified=verified, check_only=True)
        mock_logging.info.assert_called_with('Fetching %s to %s', 'someurl', 'myrelpath')
        mock_requests.get.assert_not_called()

    @patch('cwldep.os')
    @patch('cwldep.logging')
    @patch('cwldep.requests')
    @patch('cwldep.hashlib')
    def test_download_check_only_with_good_hash(self, mock_hashlib, mock_requests, mock_logging, mock_os):
        verified = {}
        locks = {'myrelpath': {'checksum': '00myhash123'}}
        mocked_open = mock_open()
        mock_os.path.isfile.return_value = True
        mock_os.path.relpath.return_value = 'myrelpath'
        mock_hashlib.sha1.return_value.hexdigest.return_value = '00myhash123'
        mocked_open = mock_open()
        with patch("cwldep.open", mocked_open):
            cwldep.download(tgt="myfile.cwl", url="someurl", version="1",
                            locks=locks, verified=verified, check_only=True)
        mock_logging.info.assert_has_calls([
            call('Fetching %s to %s', 'someurl', 'myrelpath'),
            call('Up to date: %s', 'myrelpath'),
        ])
        mock_logging.warn.assert_not_called()
        mock_requests.get.assert_called_with('someurl', stream=True)

    @patch('cwldep.os')
    @patch('cwldep.logging')
    @patch('cwldep.requests')
    @patch('cwldep.hashlib')
    def test_download_check_only_with_bad_hash(self, mock_hashlib, mock_requests, mock_logging, mock_os):
        verified = {}
        locks = {'myrelpath': {'checksum': '77badhash890'}}
        mocked_open = mock_open()
        mock_os.path.isfile.return_value = True
        mock_os.path.relpath.return_value = 'myrelpath'
        mock_hashlib.sha1.return_value.hexdigest.return_value = '00myhash123'
        mocked_open = mock_open()
        with patch("cwldep.open", mocked_open):
            cwldep.download(tgt="myfile.cwl", url="someurl", version="1",
                            locks=locks, verified=verified, check_only=True)
        mock_logging.info.assert_called_with('Fetching %s to %s', 'someurl', 'myrelpath')
        mock_logging.warn.assert_called_with('Upstream has changed: %s', 'myrelpath')
        mock_requests.get.assert_called_with('someurl', stream=True)
        mock_os.rename.assert_not_called()

    @patch('cwldep.os')
    @patch('cwldep.logging')
    @patch('cwldep.requests')
    @patch('cwldep.hashlib')
    def test_download_replace_with_bad_hash(self, mock_hashlib, mock_requests, mock_logging, mock_os):
        verified = {}
        locks = {'myrelpath': {'checksum': '77badhash890'}}
        mocked_open = mock_open()
        mock_os.path.isfile.return_value = True
        mock_os.path.relpath.return_value = 'myrelpath'
        mock_hashlib.sha1.return_value.hexdigest.return_value = '00myhash123'
        mock_requests.get.return_value.__enter__.return_value.iter_content.return_value = ['cwlVersion: v1.0']
        mocked_open = mock_open()

        with patch("cwldep.open", mocked_open):
            cwldep.download(tgt="myfile.cwl", url="someurl", version="1",
                            locks=locks, verified=verified, check_only=False)
        mocked_open.return_value.write.assert_called_with('cwlVersion: v1.0')

        mock_logging.info.assert_called_with('Fetching %s to %s', 'someurl', 'myrelpath')
        mock_logging.warn.assert_called_with('Upstream has changed: %s', 'myrelpath')
        mock_requests.get.assert_called_with('someurl', stream=True)

        mock_os.rename.assert_called_with('myfile.cwl_download_', 'myfile.cwl')
        self.assertEqual(verified['myrelpath']['checksum'], '00myhash123')
        self.assertEqual(verified['myrelpath']['installed_to'], ['myrelpath'])


class VerifyTestCase(unittest.TestCase):
    @patch('cwldep.os')
    def test_verify_not_file(self, mock_os):
        mock_os.path.isfile.return_value = False
        verified = []
        self.assertEqual(cwldep.verify(tgt="sometarget.cwl", locks=[], verified=verified), False)
        mock_os.path.relpath.assert_called_with("sometarget.cwl", mock_os.getcwd.return_value)

    @patch('cwldep.os')
    @patch('cwldep.hashlib')
    def test_verify_is_file_same_checksum(self, mock_hashlib, mock_os):
        mock_os.path.isfile.return_value = True
        mock_os.path.relpath.return_value = "myrelpath"
        mock_hashlib.sha1.return_value.hexdigest.return_value = '00myhash123'
        verified = {}

        mocked_open = mock_open()
        with patch("cwldep.open", mocked_open):
            self.assertEqual(cwldep.verify(tgt="sometarget.cwl",
                                           locks={'myrelpath': {'checksum':'00myhash123'}},
                                           verified=verified), True)
        mocked_open.assert_called_with("sometarget.cwl", "rb")

    @patch('cwldep.os')
    @patch('cwldep.hashlib')
    def test_verify_is_file_different_checksum(self, mock_hashlib, mock_os):
        mock_os.path.isfile.return_value = True
        mock_os.path.relpath.return_value = "myrelpath"
        mock_hashlib.sha1.return_value.hexdigest.return_value = '77otherhash890'
        verified = {}

        mocked_open = mock_open()
        with patch("cwldep.open", mocked_open):
            self.assertEqual(cwldep.verify(tgt="sometarget.cwl",
                                           locks={'myrelpath': {'checksum':'00myhash123'}},
                                           verified=verified), False)
        mocked_open.assert_called_with("sometarget.cwl", "rb")


class LoadNoCheckTestCase(unittest.TestCase):
    @patch('cwldep.cwltool')
    @patch('cwldep.schema_salad.ref_resolver')
    def test_load_nocheck(self, mock_ref_resolver, mock_cwltool):
        mock_loader = Mock()
        mock_workflowobj = {
            "cwlVersion": "v1.0",
            "id": "myid",
            'class': 'Workflow',
        }
        mock_cwltool.load_tool.fetch_document.return_value = mock_loader, mock_workflowobj, "uri"
        mock_document = Mock()
        mock_ref_resolver.Loader.return_value.resolve_all.return_value = mock_document, None
        mock_upstream = Mock()

        self.assertEqual(cwldep.load_nocheck(mock_upstream), (mock_document, mock_loader))


class CWLDepsTestCase(unittest.TestCase):
    @patch('cwldep.os')
    @patch('cwldep.urllib')
    @patch('cwldep.logging')
    def test_cwl_deps_unsupported_scheme(self, mock_logging, mock_urllib, mock_os):
        locks = {}
        verified = {}
        dependencies = {
            'dependencies': [
                {
                    'upstream': 'https://raw.githubusercontent.com/some.cwl'
                }
            ]
        }
        mock_urllib.parse.urlsplit.return_value = Mock(scheme='ftp')
        cwldep.cwl_deps(basedir="/tmp",
                        dependencies=dependencies,
                        locks=locks,
                        verified=verified,
                        operation="check")
        mock_logging.error.assert_called_with('Scheme %s not supported', 'ftp')

    @patch('cwldep.os')
    @patch('cwldep.urllib')
    @patch('cwldep.logging')
    @patch('cwldep.cwltool')
    @patch('cwldep.load_nocheck')
    @patch('cwldep.download')
    def test_cwl_deps_good_scheme(self, mock_download, mock_load_nocheck, mock_cwltool, mock_logging, mock_urllib, mock_os):
        locks = {}
        verified = {}
        dependencies = {
            'dependencies': [
                {
                    'upstream': 'https://raw.githubusercontent.com/some.cwl'
                }
            ]
        }
        mock_urllib.parse.urlsplit.return_value = Mock(scheme='http', path="somepath.cwl")
        mock_cwltool.load_tool.fetch_document.return_value = (None, None, None)
        mock_document = Mock()
        mock_document_loader = Mock()
        mock_load_nocheck.return_value = (mock_document, mock_document_loader)
        cwldep.cwl_deps(basedir="/tmp",
                        dependencies=dependencies,
                        locks=locks,
                        verified=verified,
                        operation="check")

        mock_download.assert_called_with(mock_os.path.join.return_value,
                                         'https://raw.githubusercontent.com/some.cwl', '', {}, {}, True)


class ExpandNsTestCase(unittest.TestCase):
    def test_expand_ns_no_colons(self):
        namespaces = {"dep": cwldep.CWLDEP_URL}
        self.assertEqual(cwldep.expand_ns(namespaces, symbol="symbol"), "symbol")

    def test_expand_ns_with_known_namespace(self):
        namespaces = {"dep": cwldep.CWLDEP_URL}
        self.assertEqual(cwldep.expand_ns(namespaces, symbol="dep:symbol"), "{}symbol".format(cwldep.CWLDEP_URL))

    def test_expand_ns_with_unknown_namespace(self):
        namespaces = {"dep": cwldep.CWLDEP_URL}
        self.assertEqual(cwldep.expand_ns(namespaces, symbol="other:symbol"), "other:symbol")


class AddDepTestCase(unittest.TestCase):
    @patch('cwldep.cwltool')
    @patch('cwldep.os')
    @patch('cwldep.ruamel')
    def test_add_dep(self, mock_ruamel, mock_os, mock_cwltool):
        """
        Tests that add_dep will add a dep namespace and dependency
        """
        mock_loader = Mock()
        mock_workflowobj = {
            "id": "myid",
            'class': 'Workflow',
        }
        mock_cwltool.load_tool.fetch_document.return_value = mock_loader, mock_workflowobj, "uri"
        mocked_open = mock_open()

        with patch("cwldep.open", mocked_open):
            cwldep.add_dep(fn="myfile.cwl",
                           upstream="some_remote_url.cwl",
                           set_version=None,
                           install_to=None)

        self.assertTrue(mock_ruamel.yaml.round_trip_dump.called)
        args, kwargs = mock_ruamel.yaml.round_trip_dump.call_args
        workflow = args[0]
        dependencies = workflow['hints']['dep:Dependencies']['dependencies']
        self.assertEqual(dependencies[0]['upstream'], "some_remote_url.cwl")
        self.assertEqual(workflow['$namespaces']['dep'], cwldep.CWLDEP_URL)

        mocked_open.assert_called_with('_myfile.cwl_', 'w')
        mock_os.rename.assert_called_with('_myfile.cwl_', 'myfile.cwl')
