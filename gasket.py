from flask import Flask
import pygit2
import pystache

from datetime import datetime

app = Flask(__name__)


class TreeModel(object):
    def __init__(self, repo, tree, name=None):
        self._repo = repo
        self._tree = tree
        self.url = u'/trees/%s' % self._tree.hex
        self.hex = self._tree.hex
        self.name = name

    def __iter__(self):
        for entry in self._tree:
            obj = entry.to_object()
            if obj.type == pygit2.GIT_OBJ_TREE:
                item = TreeModel(self._repo, obj, entry.name)
            elif obj.type == pygit2.GIT_OBJ_BLOB:
                item = BlobModel(self._repo, obj, entry.name)
            else:
                raise Exception

            yield item

class BlobModel(object):
    def __init__(self, repo, blob, name):
        self._repo = repo
        self._blob = blob
        self.name = name
        self.url = u'/blobs/%s' % self._blob.hex

class CommitModel(object):
    def __init__(self, repo, commit):
        self._repo = repo
        self._commit = commit
        self.url = u'/commits/%s' % self._commit.hex
        self.timestamp = self._commit.author.time
        self.author = self._commit.author
        self.committer = self._commit.committer
        self.hex = self._commit.hex
        self.tree = TreeModel(self._repo, self._commit.tree)

    def age(self):
        dt = datetime.fromtimestamp(self.timestamp)
        return datetime.now() - dt

    def summary(self):
        summary = self._commit.message.split('\n')[0]
        if len(summary) <= 80:
            return summary
        else:
            return summary[:77] + u'...'

    def detail(self):
        return '\n'.join(self._commit.message.split('\n')[1:]).lstrip('\n')

    def parents(self):
        return [CommitModel(parent) for parent in self._commit.parents]

    def short(self):
        return self.hex[:8]

class DiffLineModel(object):
    def __init__(self, data, old_line, new_line, kind):
        self.data = data
        self.old_line = old_line
        self.new_line = new_line
        self.kind = kind

class DiffHunkModel(object):
    def __init__(self, repo, commit, hunk):
        self._repo = repo
        self._commit = commit
        self._hunk = hunk

        self.header = self._hunk.header
        self.old_file = self._hunk.old_file
        self.new_file = self._hunk.new_file
        self.old_mode = oct(self._hunk.old_mode)
        self.new_mode = oct(self._hunk.new_mode)

    def _build_diff_hunk(self, data):
        hunk = []
        oldline_pos = self._hunk.old_start
        newline_pos = self._hunk.new_start

        ol = oldline_pos
        nl = newline_pos

        for (line, kind) in data:
            if kind == pygit2.GIT_DIFF_LINE_ADDITION:
                lm = DiffLineModel(line.rstrip('\n\r'), ol, nl, 'add')
                nl += 1
            elif kind == pygit2.GIT_DIFF_LINE_DELETION:
                lm = DiffLineModel(line.rstrip('\n\r'), ol, nl, 'del')
                ol += 1
            elif kind == pygit2.GIT_DIFF_LINE_CONTEXT:
                lm = DiffLineModel(line.rstrip('\n\r'), ol, nl, 'context')
                nl += 1
                ol += 1

            hunk.append(lm)

        return hunk

    def hunk(self):
        return self._build_diff_hunk(self._hunk.data)

class DiffModel(object):
    def __init__(self, repo, commit, diff):
        self._repo = repo
        self._commit = commit
        self._diff = diff

    def __iter__(self):
        for hunk in self._diff.changes['hunks']:
            yield DiffHunkModel(self._repo, self._commit, hunk)

class DiffHunkContextModel(object):
    def __init__(self, repo, commit, data):
        pass


@app.route('/commits')
def commits():
    head = repo.head

    commits = []
    for commit in repo.walk(head.oid, pygit2.GIT_SORT_TIME):
        commits.append(CommitModel(repo, commit))

    renderer = pystache.Renderer(file_extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    #with open('commits.html') as fh:
    #    return pystache.render(fh.read(), commits=commits)

    return renderer.render(loader.load_name('commits'), commits=commits)

@app.route('/commits/<sha1>')
def commit(sha1):
    commit = CommitModel(repo, repo[sha1])

    entries = commit.tree

    renderer = pystache.Renderer(file_extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    #with open('tree.html') as fh:
    #    return pystache.render(fh.read(), entries=entries)
    return renderer.render(loader.load_name('tree'), commit=commit, sha1=sha1, entries=entries)


@app.route('/trees/<ref>')
def tree(ref):
    i = repo[ref]
    tree = TreeModel(repo, i.hex)

    entries = tree

    renderer = pystache.Renderer(file_extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    #with open('tree.html') as fh:
    #    return pystache.render(fh.read(), entries=entries)
    return renderer.render(loader.load_name('tree'), sha1=ref, entries=entries)

@app.route('/commits/<sha1>/<filename>')
def file(sha1, filename):
    commit = repo[sha1]
    data = repo[commit.tree[filename].oid].data

    renderer = pystache.Renderer(file_extension='html', file_encoding='utf-8', search_dirs=['/home/dan/dev/gasket/templates'])
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])

    return renderer.render(loader.load_name('file'), data=data)

if __name__ == '__main__':

    repo = pygit2.Repository('/home/dan/libgit2')
    app.debug = True
    app.run()
