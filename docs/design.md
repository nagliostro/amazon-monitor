# Design: Monitor de Estoque

Fonte de verdade da interface em `docs/index.html` (GitHub Pages).

## Cores

| Token        | Claro     | Escuro    | Uso                                |
|--------------|-----------|-----------|------------------------------------|
| `--bg`       | `#F6F7F9` | `#0B0D10` | fundo (off-white / quase preto)    |
| `--surface`  | `#FFFFFF` | `#14171C` | campos, botão secundário           |
| `--text`     | `#0E1116` | `#ECEFF3` | texto principal                    |
| `--muted`    | `#5B6573` | `#8E98A6` | ardósia: texto secundário          |
| `--border`   | `#E2E5EA` | `#262B33` | divisórias e bordas                |
| `--accent`   | `#1B2A4A` | `#A9BCD6` | único acento: marinho / azul-acinzentado |
| `--on-accent`| `#FFFFFF` | `#0B0D10` | texto sobre o acento               |
| `--ok`       | `#1E7047` | `#7FD1A3` | selo "Disponível"                  |
| `--warn`     | `#7A5A12` | `#E0C27A` | avisos (captcha, faixa de preço)   |
| `--danger`   | `#B42318` | `#F19A92` | excluir                            |

O tema segue o sistema (`prefers-color-scheme`).

## Tipografia

Geist (Inter como reserva). Título 32/700, rótulos de seção 13/600 em caixa alta, corpo 16.

## Componentes

- **Botão padrão (`.btn`)**: pílula, altura 44px, largura mínima 96px e máxima 280px. Variantes:
  `primary` (acento), `secondary` (superfície com borda), `ghost`, `danger` (texto vermelho).
- **Campo (`.field`)**: retângulo arredondado de 12px, altura 56px, label flutuante dentro do campo.
- **Interruptor (`.switch`)**: 48×28 dentro de uma linha com alvo de 44px.
- **Selo (`.badge`)**: pílula pequena; verde só para "Disponível", neutro para o resto.
- **Diálogo**: centralizado no desktop, folha presa embaixo no celular (≤600px).

## Telas

1. **Conectar**: campo do token e passo a passo para criar o token.
2. **Principal**: título, linha de status (monitorando / pausado + última checagem), botão Pausar,
   ações "Checar agora" e "Enviar teste", lista de produtos e últimas execuções.
3. **Produto (diálogo)**: nome, link, faixa de preço, "só Amazon" (só em links da Amazon),
   texto de esgotado (só em outras lojas), ativo. Rodapé: Excluir, Testar alerta, Salvar.

## Decisões

- Interface só em pt-BR, porque é uma ferramenta de uso pessoal.
- Sem cards: a lista usa só divisórias, para ficar mais limpa.
