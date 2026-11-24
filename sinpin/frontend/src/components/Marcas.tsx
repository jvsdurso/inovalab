// Marcas do protótipo visual (SVG). O brasão abaixo é um DESENHO APROXIMADO do protótipo: antes de produção,
// substitua por arquivos oficiais da Identidade Padrão de Comunicação Digital do Governo Federal.
export function LogoGovBr() {
  return (
    <span className="govbr-logo" aria-label="gov.br">
      <span style={{ color: "#1351B4" }}>g</span><span style={{ color: "#FFCD07" }}>o</span><span style={{ color: "#168821" }}>v</span>
      <span style={{ color: "#1351B4" }}>.</span><span style={{ color: "#0C326F" }}>b</span><span style={{ color: "#FFCD07" }}>r</span>
    </span>
  );
}

export function LosangoGov() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <rect x="2" y="3" width="20" height="18" rx="3" fill="#168821" />
      <polygon points="12,5 20,12 12,19 4,12" fill="#FFCD07" />
      <circle cx="12" cy="12" r="3.6" fill="#1351B4" />
    </svg>
  );
}

export function Brasao() {
  return (
    <svg width="40" height="40" viewBox="0 0 100 100" fill="none" role="img" aria-label="Brasão da República Federativa do Brasil">
      <circle cx="50" cy="50" r="44" fill="#FFCD07" fillOpacity="0.18" stroke="#D97706" strokeWidth="1.2" strokeDasharray="3 2" />
      <polygon points="50,6 61,35 92,35 67,54 76,84 50,66 24,84 33,54 8,35 39,35" fill="#168821" stroke="#FFCD07" strokeWidth="2.5" strokeLinejoin="round" />
      <path d="M22 68C16 56 17 42 25 32" stroke="#15803D" strokeWidth="3" strokeLinecap="round" />
      <path d="M78 68C84 56 83 42 75 32" stroke="#15803D" strokeWidth="3" strokeLinecap="round" />
      <rect x="47" y="72" width="6" height="18" rx="2" fill="#071D41" />
      <rect x="41" y="74" width="18" height="4" rx="1.5" fill="#FFCD07" />
      <circle cx="50" cy="49" r="19" fill="#1351B4" stroke="#FFCD07" strokeWidth="2.5" />
      <circle cx="50" cy="49" r="14.5" stroke="#FFFFFF" strokeWidth="1" strokeDasharray="1.5 2.5" />
      <circle cx="50" cy="42" r="1.6" fill="#FFFFFF" /><circle cx="50" cy="56" r="1.6" fill="#FFFFFF" />
      <circle cx="44" cy="49" r="1.6" fill="#FFFFFF" /><circle cx="56" cy="49" r="1.6" fill="#FFFFFF" />
      <circle cx="52.5" cy="51.5" r="1.1" fill="#FFCD07" />
      <path d="M23 75C34 81 66 81 77 75L74 83C63 88 37 88 26 83L23 75Z" fill="#071D41" stroke="#FFCD07" strokeWidth="1.2" />
    </svg>
  );
}

export function LogoProduto({ tamanho = 36 }: { tamanho?: number }) {
  return (
    <svg width={tamanho} height={tamanho} viewBox="0 0 64 64" fill="none" role="img" aria-label="Logotipo do produto">
      <path d="M32 5L52 13V29C52 42.5 43.4 53.8 32 58C20.6 53.8 12 42.5 12 29V13L32 5Z" fill="#071D41" stroke="#FFCD07" strokeWidth="2.2" />
      <path d="M32 6.5L50.5 14V29C50.5 41.6 42.6 52.3 32 56.4V6.5Z" fill="#168821" fillOpacity="0.45" />
      <circle cx="19" cy="20" r="2.2" fill="#38BDF8" /><circle cx="45" cy="20" r="2.2" fill="#FFCD07" />
      <path d="M19 20L25 24M45 20L39 24" stroke="#7DD3FC" strokeWidth="1.5" strokeLinecap="round" />
      <path d="M32 15V41" stroke="#FFCD07" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M21.5 23H42.5" stroke="#FFCD07" strokeWidth="2.2" strokeLinecap="round" />
      <path d="M21.5 23L18 31H25L21.5 23Z" fill="#FFCD07" fillOpacity="0.9" />
      <path d="M42.5 23L39 31H46L42.5 23Z" fill="#FFCD07" fillOpacity="0.9" />
      <path d="M26.5 41H37.5" stroke="#FFCD07" strokeWidth="2.2" strokeLinecap="round" />
      <circle cx="43.5" cy="42.5" r="8.5" fill="#1351B4" stroke="#FFFFFF" strokeWidth="2.2" />
      <circle cx="43.5" cy="42.5" r="4.8" stroke="#FFCD07" strokeWidth="1.4" />
      <path d="M49.8 48.8L56.5 55.5" stroke="#FFCD07" strokeWidth="3.6" strokeLinecap="round" />
    </svg>
  );
}
