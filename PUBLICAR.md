# Como publicar no GitHub

O repositório local já tem os commits. Falta só criar o repositório no GitHub e enviar.

## 1. Antes de publicar

- Os commits e o `LICENSE` estão em nome de **Caio Marques** (`git log --format='%an <%ae>'`).

- Confirme que nada de dados reais vai junto:

  ```bash
  git ls-files
  ```

  A lista não pode ter `data/`, `backups/`, `.venv/` nem arquivos `.db`.

## 2. Criar o repositório vazio

1. Em <https://github.com/new>, nome sugerido: **`controle-reinf-atas`**.
2. Visibilidade: **Public**.
3. **Não** marque "Add a README", ".gitignore" nem "license": esses arquivos já existem aqui.
4. Clique em **Create repository**.

## 3. Enviar

Na pasta do projeto, trocando `SEU-USUARIO` pelo seu usuário do GitHub:

```bash
git remote add origin https://github.com/SEU-USUARIO/controle-reinf-atas.git
```

```bash
git branch -M main
```

```bash
git push -u origin main
```

Na primeira vez o Git pede login: o navegador abre para autorizar.

## 4. Campo "About" (engrenagem ao lado de "About", na página do repositório)

**Description:**

> Controle de obrigações acessórias: EFD-Reinf (natureza 12001 – lucros e dividendos) e saldo das atas de distribuição de lucros. Python, Streamlit e SQLite.

**Topics:**

`python` `streamlit` `sqlite` `contabilidade` `efd-reinf` `obrigacoes-acessorias` `distribuicao-de-lucros` `automacao-contabil`

## 5. Conferir

- Abra a página do repositório e veja se o README mostra as cinco capturas de tela.
- Opcional: fixe o repositório no seu perfil (Customize your pins).
