import gasket
import pygit2

def main():
    repo = pygit2.Repository('/home/dan/libgit2/')
    commit = repo.head.parents[1].parents[0].parents[0].parents[0]
    diff = commit.tree.diff(commit.parents[0].tree)
    dm = gasket.DiffModel(repo, commit, diff)

    for hunk in dm:
        print hunk.header
        for line in hunk.hunk():
            print line.old_line, line.new_line, line.kind, line.data

if __name__ == '__main__':
    main()
