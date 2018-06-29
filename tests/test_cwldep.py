from __future__ import absolute_import
import unittest
import cwldep
from mock import patch, Mock, mock_open


class FunctionsTestCase(unittest.TestCase):
    def test_expand_ns_no_colons(self):
        namespaces = {"dep": cwldep.CWLDEP_URL}
        self.assertEqual(cwldep.expand_ns(namespaces, symbol="symbol"), "symbol")

    def test_expand_ns_with_known_namespace(self):
        namespaces = {"dep": cwldep.CWLDEP_URL}
        self.assertEqual(cwldep.expand_ns(namespaces, symbol="dep:symbol"), "{}symbol".format(cwldep.CWLDEP_URL))

    def test_expand_ns_with_unknown_namespace(self):
        namespaces = {"dep": cwldep.CWLDEP_URL}
        self.assertEqual(cwldep.expand_ns(namespaces, symbol="other:symbol"), "other:symbol")

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

        with patch("__builtin__.open", mocked_open):
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
        with patch("__builtin__.open", mocked_open):
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
        with patch("__builtin__.open", mocked_open):
            self.assertEqual(cwldep.verify(tgt="sometarget.cwl",
                                           locks={'myrelpath': {'checksum':'00myhash123'}},
                                           verified=verified), False)
        mocked_open.assert_called_with("sometarget.cwl", "rb")
