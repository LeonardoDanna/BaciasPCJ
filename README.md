# Monitor de Noticias Hidricas - Bacias PCJ

Projeto em Python para monitorar portais de noticias e feeds RSS, identificar eventos relevantes relacionados a gestao hidrica nas Bacias PCJ e gerar relatorios estruturados em `.docx`, `.json` e persistencia em `SQLite`.

## Objetivo

O sistema coleta noticias de um conjunto de URLs, extrai metadados e texto, identifica sinais relevantes por palavras-chave e municipios das Bacias PCJ, classifica a criticidade e produz um relatorio diario com foco em eventos hidrologicos.

## Tecnologias utilizadas

- Python 3
- `urllib` para coleta HTTP
- `xml.etree.ElementTree` para RSS/Atom
- `beautifulsoup4` para parsing HTML
- `python-docx` para geracao do relatorio `.docx`
- `sqlite3` para persistencia local
- `logging` para rastreabilidade da execucao

Dependencias externas recomendadas:

```bash
pip3 install beautifulsoup4 python-docx
```

## Estrutura do projeto

```text
baciasPCJ/
├── baciasPCJ.py
├── urls_exemplo.txt
├── README.md
├── .gitignore
├── pcj_monitor/
│   ├── __init__.py
│   ├── app.py
│   ├── analyzer.py
│   ├── collector.py
│   ├── config.py
│   ├── database.py
│   ├── defaults.json
│   ├── logging_utils.py
│   ├── models.py
│   ├── reporting.py
│   └── utils.py
└── saida_pcj/
```

## Arquitetura

### 1. Entrada

O arquivo [urls_exemplo.txt](/Users/leonardodanna/Documents/VS/baciasPCJ/urls_exemplo.txt) contem a lista de fontes monitoradas. O sistema tambem aceita um arquivo `.json` com uma lista de URLs.

### 2. Configuracao

O arquivo [defaults.json](/Users/leonardodanna/Documents/VS/baciasPCJ/pcj_monitor/defaults.json) centraliza:

- palavras-chave do conjunto A
- palavras-chave do conjunto B
- municipios das Bacias PCJ
- termos de contexto hidrico
- dicas de URL para detectar paginas de noticia
- mapeamento de meses em portugues

Essa configuracao pode ser sobrescrita com `--config-file`.

### 3. Coleta

O modulo [collector.py](/Users/leonardodanna/Documents/VS/baciasPCJ/pcj_monitor/collector.py) faz:

- download da URL
- deteccao se a fonte e RSS/Atom ou HTML
- extracao de noticias do feed
- descoberta de links candidatos em paginas HTML
- leitura de artigos individuais
- filtragem por recencia
- progresso por fonte no terminal e no log

### 4. Analise

O modulo [analyzer.py](/Users/leonardodanna/Documents/VS/baciasPCJ/pcj_monitor/analyzer.py) faz:

- normalizacao de texto
- busca por palavras-chave dos conjuntos A e B
- identificacao de municipios
- filtro minimo de dois sinais
- classificacao de criticidade
- filtro de contexto hidrico
- deduplicacao
- resumo automatico simples

Regra atual de relevancia:

- `Alta`: conjunto A + conjunto B
- `Media`: conjunto B + municipio
- `Baixa`: pelo menos dois sinais, mas sem encaixar nos grupos acima
- noticias com apenas um unico sinal nao entram no relatorio

### 5. Saida

O modulo [reporting.py](/Users/leonardodanna/Documents/VS/baciasPCJ/pcj_monitor/reporting.py) gera:

- relatorio `.docx`
- relatorio `.json`
- destaque em negrito para termos importantes no documento
- agrupamento por municipio
- resumo consolidado da execucao

### 6. Persistencia

O modulo [database.py](/Users/leonardodanna/Documents/VS/baciasPCJ/pcj_monitor/database.py) salva cada execucao em `SQLite`.

Tabelas:

- `executions`: metadados da execucao e payload JSON bruto
- `news`: noticias relevantes encontradas
- `source_stats`: status de cada URL processada

### 7. Orquestracao

O modulo [app.py](/Users/leonardodanna/Documents/VS/baciasPCJ/pcj_monitor/app.py) integra tudo:

- le argumentos
- carrega configuracao e URLs
- escolhe a amostra aleatoria de URLs
- executa a coleta
- analisa e classifica
- gera relatorios
- grava no banco
- escreve log da execucao

O arquivo [baciasPCJ.py](/Users/leonardodanna/Documents/VS/baciasPCJ/baciasPCJ.py) e apenas o ponto de entrada.

## Fluxo do algoritmo

1. Ler o arquivo de URLs.
2. Selecionar uma amostra aleatoria de fontes, por padrao `10`.
3. Para cada fonte:
   - baixar a pagina/feed
   - identificar o tipo de conteudo
   - extrair noticias ou links candidatos
   - extrair titulo, data, fonte, texto e link
4. Filtrar noticias fora da janela de recencia.
5. Detectar termos dos conjuntos A e B e municipio.
6. Exigir pelo menos dois sinais para considerar a noticia.
7. Filtrar noticias fora do contexto hidrico.
8. Gerar resumo automatico.
9. Remover duplicatas.
10. Gerar `.docx` e `.json`.
11. Persistir tudo no banco `SQLite`.
12. Registrar a execucao em log.

## Como usar

### Execucao padrao

```bash
cd /Users/leonardodanna/Documents/VS/baciasPCJ
python3 baciasPCJ.py --urls-file urls_exemplo.txt --output-dir saida_pcj
```

Essa execucao:

- testa 10 URLs aleatorias por vez
- gera `.docx`
- gera `.json`
- grava no banco `SQLite`
- cria log em arquivo

### Rodar a lista completa

```bash
python3 baciasPCJ.py --urls-file urls_exemplo.txt --output-dir saida_pcj --sample-size 0
```

### Repetir a mesma amostra

```bash
python3 baciasPCJ.py --urls-file urls_exemplo.txt --output-dir saida_pcj --random-seed 42
```

### Usar outro banco

```bash
python3 baciasPCJ.py \
  --urls-file urls_exemplo.txt \
  --output-dir saida_pcj \
  --database-path meu_monitor.db
```

### Usar configuracao customizada

```bash
python3 baciasPCJ.py \
  --urls-file urls_exemplo.txt \
  --output-dir saida_pcj \
  --config-file minha_config.json
```

## Saidas geradas

Por padrao, na pasta [saida_pcj](/Users/leonardodanna/Documents/VS/baciasPCJ/saida_pcj):

- `relatorio_pcj_YYYYMMDD.docx`
- `relatorio_pcj_YYYYMMDD.json`
- `pcj_monitor.db`
- `logs/monitor_YYYYMMDD_HHMMSS.log`

## Como visualizar o banco

### No terminal

```bash
sqlite3 /Users/leonardodanna/Documents/VS/baciasPCJ/saida_pcj/pcj_monitor.db
```

Comandos uteis:

```sql
.tables
SELECT id, generated_at, total_relevant_news FROM executions ORDER BY id DESC;
SELECT titulo, municipio, classificacao, link FROM news ORDER BY id DESC LIMIT 20;
SELECT url, status, articles_found FROM source_stats ORDER BY id DESC LIMIT 20;
```

### No VS Code

Com uma extensao como `SQLite Viewer`, abra o arquivo:

[pcj_monitor.db](/Users/leonardodanna/Documents/VS/baciasPCJ/saida_pcj/pcj_monitor.db)

e navegue nas tabelas:

- `executions`
- `news`
- `source_stats`

## Logs

Cada execucao gera um log separado em:

[saida_pcj/logs](/Users/leonardodanna/Documents/VS/baciasPCJ/saida_pcj/logs)

O log registra:

- progresso `1/10`, `2/10`, etc.
- falhas de acesso e parser
- total de noticias por fonte
- caminho dos arquivos gerados
- `execution_id` gravado no banco

## Boas praticas

- manter `urls_exemplo.txt` focado em fontes confiaveis
- testar primeiro com `--sample-size 10`
- revisar periodicamente `defaults.json`
- criar parsers especificos para portais importantes se a extracao generica comecar a falhar

## Limitações atuais

- a extracao HTML ainda e generica
- o resumo e extrativo simples
- a deduplicacao usa principalmente titulo + URL
- a identificacao de municipio depende de mencao textual explicita

## Proximos passos recomendados

- criar parsers especificos por portal
- adicionar consultas ao banco via CLI
- criar testes automatizados para classificacao e parsing
- agendar execucao diaria
- adicionar exportacao para CSV ou dashboard
