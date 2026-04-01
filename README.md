# Monitor de Notícias Hídricas — Bacias PCJ

Sistema de monitoramento automático de notícias sobre recursos hídricos nas Bacias PCJ (Piracicaba, Capivari e Jundiaí). Coleta conteúdo de portais e feeds RSS, classifica eventos por criticidade e gera relatórios com análise de tópicos via BERTopic.

## Instalação

```bash
pip install beautifulsoup4 python-docx bertopic plotly sentence-transformers
```

## Como usar

```bash
# 10 URLs aleatórias (padrão)
python baciasPCJ.py --urls-file urls_exemplo.txt

# Mais URLs
python baciasPCJ.py --urls-file urls_exemplo.txt --sample-size 30

# Todas as URLs
python baciasPCJ.py --urls-file urls_exemplo.txt --sample-size 0

# Amostra reproduzível
python baciasPCJ.py --urls-file urls_exemplo.txt --sample-size 20 --random-seed 42
```

> BERTopic precisa de pelo menos 5 notícias relevantes para modelar tópicos. Use `--sample-size 30` ou mais.

## Saídas

Geradas em `saida_pcj/` ao final de cada execução:

| Arquivo | Conteúdo |
|---|---|
| `relatorio_pcj_YYYYMMDD-N.docx` | Relatório Word formatado com resumo, destaques e seção de tópicos |
| `relatorio_pcj_YYYYMMDD-N.json` | Payload completo para integração com outros sistemas |
| `relatorio_pcj_YYYYMMDD-N.csv` | Planilha com todas as notícias relevantes |
| `relatorio_pcj_YYYYMMDD-N.html` | Dashboard interativo com gráficos Plotly e análise BERTopic |
| `pcj_monitor.db` | Histórico de execuções em SQLite |
| `logs/monitor_YYYYMMDD_HHMMSS.log` | Log detalhado da execução |

Abra o `.html` no navegador para ver os gráficos.

## Dashboard HTML

O dashboard gerado inclui:

- Distribuição de criticidade (Alta / Média / Baixa)
- Municípios PCJ mais citados
- Frequência de palavras-chave detectadas
- Fontes com mais notícias relevantes
- Score de relevância PCJ por notícia
- Tópicos BERTopic com palavras principais, heatmap e distribuição
- Tabela de alertas de possíveis falsos positivos

## Classificação de relevância

Uma notícia é incluída no relatório se tiver pelo menos dois sinais:

| Classificação | Critério |
|---|---|
| **Alta** | Entidade PCJ (conjunto A) + evento hídrico (conjunto B) |
| **Média** | Evento hídrico (conjunto B) + município PCJ identificado |
| **Baixa** | Dois ou mais sinais, mas sem encaixar nos grupos acima |

Notícias com apenas um sinal ou sem contexto hídrico são descartadas.

**Conjunto A** (entidades): Cantareira, PCJ, Sistema Cantareira, Comitês PCJ, Agência PCJ, Sérgio Razera, reservatórios nomeados.

**Conjunto B** (eventos): chuva, seca, enchente, alagamento, vazamento, racionamento, estiagem, poluição, contaminação, tempestade, mortandade de peixes, falta de água.

## Estrutura do projeto

```
baciasPCJ/
├── baciasPCJ.py              # Ponto de entrada
├── urls_exemplo.txt          # Lista de URLs monitoradas
├── pcj_monitor/
│   ├── app.py                # Orquestrador principal e CLI
│   ├── collector.py          # Coleta via RSS e HTML
│   ├── analyzer.py           # Classificação de relevância e tópicos
│   ├── topic_modeling.py     # Integração BERTopic
│   ├── visualization.py      # Dashboard HTML com Plotly
│   ├── reporting.py          # Geração de .docx, .json e .csv
│   ├── database.py           # Persistência SQLite
│   ├── config.py             # Carregamento de configuração
│   ├── models.py             # Modelos de dados
│   ├── utils.py              # Utilitários de texto e URL
│   ├── logging_utils.py      # Configuração de logs
│   └── defaults.json         # Configuração padrão
└── saida_pcj/                # Relatórios gerados (ignorados pelo git)
```

## Argumentos CLI

| Argumento | Padrão | Descrição |
|---|---|---|
| `--urls-file` | obrigatório | Arquivo `.txt` ou `.json` com URLs |
| `--output-dir` | `saida_pcj` | Diretório de saída |
| `--sample-size` | `10` | Quantidade de URLs por execução (0 = todas) |
| `--random-seed` | — | Semente para amostra reproduzível |
| `--recent-days` | `7` | Janela de recência em dias |
| `--per-html-limit` | `15` | Máximo de links seguidos por portal |
| `--config-file` | — | JSON para sobrescrever `defaults.json` |
| `--database-path` | — | Caminho do SQLite (padrão: `saida_pcj/pcj_monitor.db`) |

## Configuração

Edite `pcj_monitor/defaults.json` para ajustar palavras-chave, municípios monitorados e termos de contexto hídrico. Use `--config-file` para passar uma configuração alternativa sem modificar o padrão.

## Banco de dados

```bash
sqlite3 saida_pcj/pcj_monitor.db
```

```sql
-- Execuções recentes
SELECT id, generated_at, total_relevant_news FROM executions ORDER BY id DESC;

-- Notícias encontradas
SELECT titulo, municipio, classificacao FROM news ORDER BY id DESC LIMIT 20;

-- Status das fontes
SELECT url, status, articles_found FROM source_stats ORDER BY id DESC LIMIT 20;
```

## Limitações

- Extração HTML genérica — portais com estrutura não convencional podem retornar 0 artigos
- Resumo extrativo simples (primeiras 3 frases)
- Identificação de município depende de menção textual explícita
- Deduplicação por título + URL (duplicatas com URLs diferentes passam)
