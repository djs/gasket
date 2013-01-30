import os
import gasket
import unittest
import tempfile
import pygit2

from gasket import TreeModel
from gasket import CommitModel

class FlaskrTestCase(unittest.TestCase):

    def setUp(self):
        gasket.app.config['TESTING'] = True
        gasket.app.repo = pygit2.Repository('/home/dan/libgit2')
        self.app = gasket.app.test_client()

    def tearDown(self):
        pass

    def test_empty_db(self):
        rv = self.app.get('/tree/development')

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.app = gasket.app.test_client()
        gasket.app.repo = pygit2.Repository('/home/dan/libgit2')
        self.repo = pygit2.Repository('/home/dan/libgit2')

    def test_tree_path(self):
        head = gasket.app.repo.head

        gt = head.tree


        tree = TreeModel(gasket.app.repo, head, gt, '', 'HEAD')

        entries = tree

        commit = CommitModel(gasket.app.repo, head, None)

if __name__ == '__main__':
    unittest.main()
