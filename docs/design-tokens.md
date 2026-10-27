# Tokens de design do docs/index.html

Origem: repositório do guia conceitual `capstone-insper/202602_MCKINSEY_DiagnosticEngineDataRequest_Docs`, clonado em 2026-10-27. O guia adotou o QuantumBlack Design System (QBDS, Apache 2.0) em 13/10/2026; a paleta Azure Mono em `docs/identity/akme-tokens.css` ficou como histórico e não é usada aqui. Fontes de verdade lidas: `styles/globals.css` (tema do QBDS instalado pelo registry), `app/globals.css`, `app/(guia)/layout.tsx`, `components/ui/{card,badge,table}.tsx`, `components/guide/{callout,diagrams/flow,diagrams/README}.tsx` e `DESIGN.md`.

Regra do QBDS que o HTML segue: tokens semânticos sempre (`surface-*` para fundo de página, `fill-*` para conteúdo e componentes, `text-*` para texto, `border-*` para traços, `status-*` só para preenchimentos e bordas de estado). O acento QB marca apenas nós focais ou selecionados.

## Primitivos

| Token | Valor |
|---|---|
| mist-50 | oklch(100% 0 0) |
| mist-100 | oklch(98.54% 0.0013 286.38) |
| mist-200 | oklch(97.24% 0.0011 197.14) |
| mist-300 | oklch(96.37% 0.0017 247.84) |
| mist-400 | oklch(94.49% 0.0025 228.79) |
| mist-500 | oklch(93% 0.0035 247.86) |
| mist-900 | oklch(87.46% 0.0053 247.88) |
| slate-100 | oklch(33.4% 0.0181 272.2) |
| slate-300 | oklch(30.29% 0.0203 273.16) |
| slate-400 | oklch(28.68% 0.0206 273.08) |
| slate-500 | oklch(27.1% 0.0227 273.84) |
| slate-600 | oklch(25.44% 0.0231 273.73) |
| slate-700 | oklch(23.76% 0.0235 273.59) |
| slate-800 | oklch(22.43% 0.022 272.68) |
| slate-900 | oklch(20.64% 0.0205 271.56) |
| slate-950 | oklch(18.46% 0.0187 274.71) |
| qb-accent | oklch(69.89% 0.1572 238.91) |
| sky-500 / sky-600 / sky-700 / sky-400 | #0ea5e9 / #0284c7 / #0369a1 / #38bdf8 |
| green-400 / green-600 / green-700 | #4ade80 / #16a34a / #15803d |
| amber-400 / amber-500 / amber-600 / amber-700 | #fbbf24 / #f59e0b / #d97706 / #b45309 |
| red-400 / red-600 / red-700 | #f87171 / #dc2626 / #b91c1c |

Opacidades de slate-900 (claro) e mist-50 (escuro): 6, 8, 10, 16, 24, 38, 50, 60 e 88, expressas como `calc(n / 255)` no canal alfa.

## Semânticos

| Token | Claro | Escuro |
|---|---|---|
| surface-base (fundo da página) | mist-100 | slate-900 |
| surface-primary (sidebar, cabeçalho, cartões) | mist-50 | slate-800 |
| surface-secondary | mist-400 | slate-700 |
| fill-onsurface-ui-1 (cartão de contraste baixo, blocos de código) | mist-100 | slate-600 |
| fill-onsurface-ui-2 (cartão de contraste alto) | mist-300 | slate-300 |
| fill-subtle | slate-900 a 6% | mist-50 a 6% |
| fill-muted | slate-900 a 8% | mist-50 a 8% |
| fill-active (botão primário, marcador de passo) | slate-950 | mist-50 |
| text-primary | slate-900 a 88% | mist-50 a 88% |
| text-secondary | slate-900 a 60% | mist-50 a 60% |
| text-tertiary | slate-900 a 50% | mist-50 a 50% |
| text-primary-inverse | mist-50 a 88% | slate-900 a 88% |
| text-information / error / warning / success | sky-700 / red-700 / amber-700 / green-700 | sky-400 / red-400 / amber-400 / green-400 |
| border-divider | slate-900 a 10% | mist-50 a 8% |
| border-tertiary | slate-900 a 16% | mist-50 a 16% |
| border-secondary | slate-900 a 24% | mist-50 a 38% |
| border-active | slate-950 | mist-50 |
| border-status-focus | sky-500 | sky-400 |
| status-success / error / warning / information | green-600 / red-600 / amber-600 / sky-600 | green-400 / red-400 / amber-400 / sky-400 |
| brand qb-accent | oklch(69.89% 0.1572 238.91) nos dois modos | |

## Tipografia

Famílias: Inter para tudo (títulos, corpo, interface), Roboto Mono para código e identificadores. O guia serve as fontes localmente via next/font; o HTML carrega do Google Fonts com fallback de sistema.

| Papel | Classe QBDS | Tamanho / entrelinha | Peso | Tracking |
|---|---|---|---|---|
| Título de seção | headings-h2-semibold | 24 / 32 px | 600 | -0.096px |
| Subtítulo | headings-h3-regular | 20 / 28 px | 400 | 0 |
| Corpo grande | paragraph-large-primary | 16 / 24 px | 400 | |
| Corpo | paragraph-regular-primary | 14 / 20 px | 400 | -0.028px |
| Corpo enfatizado | paragraph-regular-emphasised-600 | 14 / 20 px | 600 | |
| Rótulo pequeno | label-small-primary | 12 / 16 px | 400 | 0 |
| Código | paragraph-code-text | 14 / 24 px Roboto Mono | 400 | |
| Rótulo de tipo nos diagramas | KIND_CLASS | 10 px, uppercase | 500 | 0.12em |

Escala completa: 12, 14, 16, 20, 24, 32, 40, 48, 56 px. Corpo das páginas: 16 / 24 px. Parágrafos limitados a 68ch. Rótulos de grupo da sidebar em uppercase 12 px text-tertiary.

## Espaçamento e layout

- Base de 4 px (escala do Tailwind). Inset dos cartões: 28 px (padrão) ou 24 px (sm).
- Cabeçalho fixo de 56 px com borda inferior border-divider e fundo surface-primary a 95% com blur.
- Sidebar de 16rem (18rem no celular, offcanvas), fundo surface-primary, cabeçalho de 56 px, itens com padding 8 px e altura automática.
- Coluna de conteúdo centrada com largura máxima de 52rem, padding 16 px no celular e 28 px lateral, 36 px vertical no desktop.
- Ritmo vertical do corpo: 16 px entre blocos, 40 px antes de h2, 32 px antes de h3.
- Passos numerados: marcador quadrado de 28 px com fill-active e texto inverso, trilho de 1 px border-tertiary à esquerda.

## Raio, sombras e movimento

- Cantos retos em todos os componentes (tokens de raio do QBDS valem 0). Único raio: `round` = 9999px em badges, dots e marcadores circulares.
- elevation-0: `0 1px 1px 0 shade-t, 0 0 1px 0 shade` (cartões). elevation-1: `0 2px 4px 1px shade-t-01, 0 1px 4px 0 shade-01`. elevation-2: `0 4px 8px 0 shade-t-02, 0 2px 4px -1px shade-02`. No claro, shade-t = slate-900 a 8% e shade = slate-900 a 38%; no escuro, slate-900 a 88%.
- Camadas de estado: hover = 8% e pressed = 16% da cor de texto sobre o fundo.
- Transições de 140 a 200 ms; desativadas com `prefers-reduced-motion`.

## Componentes reproduzidos no HTML

- Card: fundo fill-onsurface-ui-1 (contraste baixo) ou ui-2 (alto), elevation-0, título h2 ou h3, descrição em text-secondary.
- Badge: pílula de 24 px (20 px em sm), label-small-primary, padding horizontal 8 px. Variantes: high-emphasis (fill-active sobre texto inverso), alternative (fill-muted e text-secondary), error, warning e success (status-* com texto inverso), outline opcional de 1 px.
- Tag de status: ícone de status mais texto, como em "Pronto".
- Callout: faixa com ícone de status, título e corpo em text-secondary; variantes nota (information), atenção (warning) e exemplo (text-secondary).
- Tabela: cabeçalho com borda inferior border-tertiary, texto text-secondary, 14 / 20 px, células com alinhamento superior.
- Busca: campo com ícone e borda border-secondary, foco com anel border-status-focus de 3 px.

## Convenções dos diagramas e do grafo

Do `flow.tsx` e do README dos diagramas: nós como cartões com ícone, rótulo de tipo pequeno em uppercase, título e descrição; tons neutral (border-tertiary sobre surface-primary), accent (qb-accent, só para nós focais), warning e success (status-*). Curvas tracejadas com ponta de seta; texto das arestas com halo da cor do fundo. O grafo de ontologia do guia usa nós circulares com rótulo e arestas curvas rotuladas, sem cor por entidade, com o acento QB apenas no nó em foco. Direção aprovada: legível nos dois temas e em largura de celular; nenhuma dependência além dos tokens. Este HTML usa D3 apenas para o layout de forças, com arraste e zoom simples, e mantém equivalente textual (lista de classes e relações) acessível por teclado.

## Regras editoriais

Português do Brasil, sem travessão. Estados sempre com texto e ícone, nunca só com cor. Ícones do guia são Material Symbols Sharp; o HTML usa SVG inline de traço único para não depender da fonte de ícones.
