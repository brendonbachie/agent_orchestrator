# changelog-builder

Gera e atualiza o CHANGELOG.md com base no histórico de commits.

## Responsabilidades

- Lê `git log` desde o último tag de versão
- Categoriza commits em Added, Changed, Fixed, Removed seguindo Keep a Changelog
- Insere a nova seção no topo do CHANGELOG.md sem apagar o histórico

## Quando usar

Chame ao preparar um release ou ao criar um pull request para a branch principal.

## Comportamento esperado

- Agrupa commits por tipo (feat, fix, chore, etc.) se seguirem Conventional Commits
- Ignora commits de merge e chore automáticos (bump de versão, CI)
- Não inventa funcionalidades — usa apenas o que está nos commits
