#!/usr/bin/env bash
# Autosave: guarda um snapshot da árvore de trabalho em refs/autosave/<branch>,
# sem criar commit na branch nem mexer no índice. Não vai no push (só refs/heads).
#
# Ver snapshots:      git log --oneline refs/autosave/main
# Diff contra agora:  git diff refs/autosave/main
# Recuperar arquivo:  git checkout refs/autosave/main -- caminho/do/arquivo
cd "$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
git rev-parse -q --verify HEAD >/dev/null || exit 0

branch=$(git symbolic-ref --short -q HEAD || echo detached)
ref="refs/autosave/$branch"
git_dir=$(git rev-parse --git-dir)
tmp_index="$git_dir/autosave-index"

# Índice temporário: copia o real (preserva stat cache) e adiciona tudo nele
cp "$git_dir/index" "$tmp_index" 2>/dev/null
tree=$(GIT_INDEX_FILE="$tmp_index" sh -c 'git add -A && git write-tree') || { rm -f "$tmp_index"; exit 0; }
rm -f "$tmp_index"

last=$(git rev-parse -q --verify "$ref^{tree}" || git rev-parse "HEAD^{tree}")
[ "$tree" = "$last" ] && exit 0

parent=$(git rev-parse -q --verify "$ref" || git rev-parse HEAD)
commit=$(git commit-tree "$tree" -p "$parent" -m "autosave: $(date '+%Y-%m-%d %H:%M:%S')") || exit 0
git update-ref "$ref" "$commit"
