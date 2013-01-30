from flask import Flask
from flask import abort
from flask import request
from flask import url_for
import pygit2
import pystache

from datetime import datetime
from math import ceil
from markdown import markdown
import os.path

#from flask_debugtoolbar import DebugToolbarExtension

app = Flask(__name__)
#app.config['SECRETKEY'] = '24wejfhdsjfhwfgsfdsghfsdf'
#toolbar = DebugToolbarExtension(app)


class TreeModel(object):
    def __init__(self, repo, commit, tree, name, ref):
        self._repo = repo
        self._tree = tree
        self._commit = commit
        self._ref = ref
        self._path = name
        self.url = url_for('summary', ref=self._ref, path=self._path)
        self.hex = self._tree.hex
        self.name = os.path.basename(name)
        self.type = 'folder-close'

    def _get_subpath(self, entry):
        if self.name == '':
            return entry
        else:
            return '/'.join([self._path, entry])

    def __iter__(self):
        directories = [entry for entry in self._tree if entry.filemode == pygit2.GIT_FILEMODE_TREE]
        files = [entry for entry in self._tree if entry.filemode != pygit2.GIT_FILEMODE_TREE]

        for entry in directories + files:
            obj = entry.to_object()
            if obj.type == pygit2.GIT_OBJ_TREE:
                item = TreeModel(self._repo, self._commit, obj, self._get_subpath(entry.name), self._ref)
            elif obj.type == pygit2.GIT_OBJ_BLOB:
                item = BlobModel(self._repo, self._commit, obj, self._get_subpath(entry.name), self._ref)
            else:
                raise Exception

            yield item

    def __getitem__(self, key):
        # pygit2 currently returns TypeError when a TreeEntry does not have a key, so mask this
        # and return the correct exception
        try:
            return BlobModel(self._repo, self._commit, self._tree[key].to_object(), key, self._ref)
        except TypeError:
            raise KeyError

    def breadcrumbs(self):
        crumbs = []
        for i, x in enumerate(self._path.split('/')):
            item = {}
            item['entry'] = x
            item['url'] = url_for('summary', ref=self._ref, path='/'.join(self._path.split('/')[:i+1]))
            crumbs.append(item)

        crumbs[-1]['class'] = 'active'

        return crumbs



class BlobModel(object):
    def __init__(self, repo, commit, blob, name, ref):
        self._repo = repo
        self._blob = blob
        self._ref = ref
        self.name = os.path.basename(name)
        self.path = name
        self.url = url_for('file', ref=self._ref, filename=self.path)
        self.data = self._blob.data
        self.type = 'file'

class CommitModel(object):
    def __init__(self, repo, commit, ref):
        self._repo = repo
        self._commit = commit
        self._ref = ref
        self.url = url_for('commit', sha1=self._commit.hex)
        self.timestamp = self._commit.author.time
        self.author = self._commit.author
        self.committer = self._commit.committer
        self.hex = self._commit.hex
        self.tree = TreeModel(self._repo, self._commit, self._commit.tree, '/', self._ref)

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
        return [CommitModel(self._repo, parent, self._ref) for parent in self._commit.parents]

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
                lm = DiffLineModel(line.rstrip('\n\r'), '', nl, 'add')
                nl += 1
            elif kind == pygit2.GIT_DIFF_LINE_DELETION:
                lm = DiffLineModel(line.rstrip('\n\r'), ol, '', 'del')
                ol += 1
            elif kind == pygit2.GIT_DIFF_LINE_CONTEXT:
                lm = DiffLineModel(line.rstrip('\n\r'), ol, nl, 'context')
                nl += 1
                ol += 1

            hunk.append(lm)

        return hunk

    @property
    def lines(self):
        return self._build_diff_hunk(self._hunk.data)

class DiffFileModel(object):
    def __init__(self, repo, commit, diff, hunks):
        self._repo = repo
        self._commit = commit
        self._diff = diff
        self._hunks = hunks

        self.old_file = self._hunks[0].old_file
        self.new_file = self._hunks[0].new_file

    @property
    def hunks(self):
        hm = []
        for hunk in self._hunks:
            hm.append(DiffHunkModel(self._repo, self._commit, hunk))

        return hm


class DiffModel(object):
    def __init__(self, repo, commit, diff):
        self._repo = repo
        self._commit = commit
        self._diff = diff

    @property
    def files(self):
        df = []
        for old_file in [x[0] for x in self._diff.changes['files']]:
            hunks = [hunk for hunk in self._diff.changes['hunks'] if hunk.old_file == old_file]
            df.append(DiffFileModel(self._repo, self._commit, self._diff, hunks))

        return df


class DiffHunkContextModel(object):
    def __init__(self, repo, commit, data):
        pass

class PageModel(object):
    def __init__(self, page, active, url):
        self.page = page
        self.active = active
        self.url = url

class PaginationModel(object):
    def __init__(self, items, limit, current, depth, url_base):
        self._items = items
        self._limit = limit
        self._current = current
        self._depth = depth
        self._pages = int(ceil(items / limit))
        self._url_base = url_base

        assert depth % 2 == 1
        #self.current_page = (self._current / self._items) + 1
        self._current_page = current

    def __iter__(self):
        for page in xrange(self._pages):
            if page == self._current:
                active = 'active'
            else:
                active = ''
            yield PageModel(page, active, url_for(self._url_base, page=page, limit=self._limit))

class NextPageModel(PageModel):
    def __init__(self, page, active, url):
        PageModel.__init__(self, page, active, url)
        self.text = 'Next'

class PrevPageModel(PageModel):
    def __init__(self, page, active, url):
        PageModel.__init__(self, page, active, url)
        self.text = 'Previous'

class NextPrevPaginationModel(PaginationModel):
    def __iter__(self):
        pass

class TagModel(object):
    def __init__(self, ref):
        self.ref = ref
        self.name = self.ref.replace('refs/tags/', '', 1)

class BranchModel(object):
    def __init__(self, ref):
        self.ref = ref
        self.name = self.ref.replace('refs/heads/', '', 1)



@app.route('/')
@app.route('/tree/<ref>/<path:path>')
@app.route('/tree/<ref>')
def summary(ref=None, path=''):
    if ref is None:
        head = app.repo.head
    else:
        head = app.repo.revparse_single(ref)


    gt = head.tree
    if path != '':
        gt = head.tree[path].to_object()


    tree = TreeModel(app.repo, head, gt, path, ref)

    entries = tree

    commit = CommitModel(app.repo, head, None)

    #branch = repo.lookup_reference('HEAD').target.replace('refs/heads/', '', 1)
    branch = ref
    branches = [BranchModel(x) for x in app.repo.listall_references() if x.startswith('refs/heads/')]
    tags = [TagModel(x) for x in app.repo.listall_references() if x.startswith('refs/tags/')]

    try:
        readme = tree['README.md']
        readme.data = markdown(readme.data)
    except KeyError:
        readme = ''


    renderer = pystache.Renderer(file_extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    #with open('tree.html') as fh:
    #    return pystache.render(fh.read(), entries=entries)
    return renderer.render(loader.load_name('summary'), commit=commit, entries=entries, branch=branch, branches=branches, tags=tags, readme=readme)

@app.route('/commits/<ref>')
@app.route('/commits/')
def commits(ref=None):
    try:
        page = int(request.args.get('page', '1'))
    except ValueError:
        abort(400)

    try:
        limit = int(request.args.get('limit', '30'))
    except ValueError:
        abort(400)

    if ref == None:
        head = app.repo.head
    else:
        head = app.repo.revparse_single(ref)
    commits = []

    for index, commit in enumerate(app.repo.walk(head.oid, pygit2.GIT_SORT_TIME)):
        if index >= (limit * (page - 1)) and index < (limit * page):
            commits.append(CommitModel(app.repo, commit, ref))
        elif index >= (limit * page):
            pass

    pagination = PaginationModel(index, limit, page, 5, 'commits')

    renderer = pystache.Renderer(file_extension='html', search_dirs=['/home/dan/dev/gasket/templates'], string_encoding='utf-8')
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    #with open('commits.html') as fh:
    #    return pystache.render(fh.read(), commits=commits)

    return renderer.render(loader.load_name('commits'), commits=commits, pagination=pagination)

@app.route('/commit/<sha1>')
def commit(sha1):
    commit = CommitModel(app.repo, app.repo[sha1], sha1)

    diff = app.repo[sha1].tree.diff(app.repo[sha1].parents[0].tree)
    dm = DiffModel(app.repo, commit, diff)

    renderer = pystache.Renderer(file_extension='html', search_dirs=['/home/dan/dev/gasket/templates'], string_encoding='utf-8')
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    #with open('tree.html') as fh:
    #    return pystache.render(fh.read(), entries=entries)
    return renderer.render(loader.load_name('commit'), commit=commit, sha1=sha1, diff=dm)

@app.route('/trees/<ref>')
def tree(ref):
    i = app.repo[ref]
    tree = TreeModel(app.repo, i, i.tree, None, ref)

    entries = tree

    renderer = pystache.Renderer(file_extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])
    #with open('tree.html') as fh:
    #    return pystache.render(fh.read(), entries=entries)
    return renderer.render(loader.load_name('tree'), sha1=ref, entries=entries)

@app.route('/commits/<ref>/<path:filename>')
def file(ref, filename):
    commit = app.repo.revparse_single(ref)
    data = app.repo[commit.tree[filename].oid].data

    renderer = pystache.Renderer(file_extension='html', string_encoding='utf-8', search_dirs=['/home/dan/dev/gasket/templates'])
    loader = pystache.loader.Loader(extension='html', search_dirs=['/home/dan/dev/gasket/templates'])

    return renderer.render(loader.load_name('file'), data=data)

if __name__ == '__main__':

    app.repo = pygit2.Repository('/home/dan/libgit2')
    app.debug = True
    app.run(host='0.0.0.0')
