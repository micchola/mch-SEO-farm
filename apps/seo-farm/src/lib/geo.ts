// MCH pSEO — costruzione JSON-LD (GEO/AEO) per le pagine generiche.
// Viene chiamato da ogni page [slug].astro e passato a Base per l'iniezione nel <head>.
// Output pronto per schema.org: Article + BreadcrumbList + FAQPage (dall'FAQ backfillato).

export type GeoType = "settore" | "oss" | "confronto";

export interface GeoInput {
  type: GeoType;
  slug: string;
  md: string;
  domain?: string;
}

const TYPE_LABEL: Record<GeoType, string> = {
  settore: "Software per Settore",
  oss: "Alternative Open Source",
  confronto: "Confronti",
};

function titleOf(slug: string, type: GeoType): string {
  if (type === "settore") {
    const [cat, sec] = slug.split("-");
    return `I 10 migliori software ${cat} per ${sec} in Italia (2026)`;
  }
  if (type === "oss") return `Alternative open source a ${slug} (2026)`;
  const [a, b] = slug.split("-");
  return `${a} vs ${b}: quale scegliere nel 2026`;
}

function descOf(slug: string, type: GeoType): string {
  if (type === "settore") {
    const [cat, sec] = slug.split("-");
    return `Confronto, prezzi e pros/contro dei migliori software ${cat} per ${sec} in Italia nel 2026.`;
  }
  if (type === "oss") return `Le migliori alternative open source a ${slug}: confronto, licenze e come hosteggiarle.`;
  const [a, b] = slug.split("-");
  return `Confronto diretto tra ${a} e ${b} nel 2026: prezzo, funzionalità e quale scegliere.`;
}

// Estrae le FAQ dalla sezione "## FAQ" aggiunta dal backfill (domande in **bold**, risposta sotto).
function parseFaq(md: string): { q: string; a: string }[] {
  const start = md.indexOf("## FAQ");
  if (start < 0) return [];
  let rest = md.slice(start + "## FAQ".length);
  const stop = rest.search(/^## /m);
  if (stop >= 0) rest = rest.slice(0, stop);
  const parts = rest.split(/\*\*(.+?)\*\*/);
  const faqs: { q: string; a: string }[] = [];
  for (let i = 1; i < parts.length; i += 2) {
    const q = parts[i].trim();
    const a = (parts[i + 1] || "").trim().replace(/^[\n]+/, "").split(/\n{2,}/)[0].trim();
    if (q && a) faqs.push({ q, a });
  }
  return faqs;
}

export function buildGeoJsonLd({ type, slug, md, domain }: GeoInput): object[] {
  const root = domain || "https://mch-seo-farm.vercel.app";
  const out: object[] = [];

  out.push({
    "@context": "https://schema.org",
    "@type": "Article",
    headline: titleOf(slug, type),
    description: descOf(slug, type),
    inLanguage: "it-IT",
    dateModified: new Date().toISOString().slice(0, 10),
    url: `${root}/${type}/${slug}`,
    wordCount: md.split(/\s+/).filter(Boolean).length,
    publisher: { "@type": "Organization", name: "MCH pSEO" },
  });

  out.push({
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      { "@type": "ListItem", position: 1, name: "Home", item: root },
      { "@type": "ListItem", position: 2, name: TYPE_LABEL[type], item: `${root}/${type}` },
      { "@type": "ListItem", position: 3, name: titleOf(slug, type) },
    ],
  });

  const faqs = parseFaq(md);
  if (faqs.length) {
    out.push({
      "@context": "https://schema.org",
      "@type": "FAQPage",
      mainEntity: faqs.map((f) => ({
        "@type": "Question",
        name: f.q,
        acceptedAnswer: { "@type": "Answer", text: f.a },
      })),
    });
  }
  return out;
}
