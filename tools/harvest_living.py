"""Find official pages for people already living in each country, for the living lane.

    python -m tools.harvest_living                 # every country
    python -m tools.harvest_living --only=UK,CA    # just these

Starts from each government's own hub pages for people who have arrived, takes
the links those pages carry on their own sites, sorts them into topics by words
in the link and its text (in the country's languages), and fetches the best
candidates through the product's fetcher, which honours robots.txt. Writes the
shortlist to tools/living_candidates.json for a person to review before
anything is seeded. Nothing is written to the registry here.
"""
from __future__ import annotations

import json
import re
import sys
from urllib.parse import urljoin, urlparse

sys.path.insert(0, ".")

from migragent.fetcher import Fetcher  # noqa: E402

HUBS = {
    "UK": ["https://www.gov.uk/browse/visas-immigration/settle-in-the-uk", "https://www.gov.uk/browse/visas-immigration",
           "https://www.gov.uk/browse/working", "https://www.gov.uk/browse/housing-local-services"],
    "CA": ["https://www.canada.ca/en/immigration-refugees-citizenship/services/new-immigrants.html",
           "https://www.canada.ca/en/immigration-refugees-citizenship/services/new-immigrants/new-life-canada.html"],
    "FR": ["https://www.service-public.gouv.fr/particuliers/vosdroits/N110",
           "https://www.service-public.gouv.fr/particuliers/vosdroits/N19811"],
    "ES": ["https://www.inclusion.gob.es/web/migraciones/", "https://extranjeros.inclusion.gob.es/es/"],
    "AE": ["https://u.ae/en/information-and-services", "https://u.ae/en/information-and-services/visa-and-emirates-id"],
    "DE": ["https://www.bamf.de/EN/Themen/Integration/integration-node.html",
           "https://www.bamf.de/EN/Themen/MigrationAufenthalt/migrationaufenthalt-node.html"],
    "IT": ["https://integrazionemigranti.gov.it/en-gb/", "https://integrazionemigranti.gov.it/it-it/"],
    "PT": ["https://aima.gov.pt/pt", "https://eportugal.gov.pt/en/inicio"],
    "SA": ["https://my.gov.sa/en", "https://www.moi.gov.sa/"],
    "IE": ["https://www.irishimmigration.ie/", "https://www.citizensinformation.ie/en/moving-country/moving-to-ireland/"],
    "SE": ["https://www.migrationsverket.se/English/Private-individuals.html",
           "https://www.skatteverket.se/servicelankar/otherlanguages/inenglishengelska.4.12815e4f14a62bc048f4edc7.html"],
    "SG": ["https://www.ica.gov.sg/reside", "https://www.mom.gov.sg/passes-and-permits"],
    "NZ": ["https://www.immigration.govt.nz/new-zealand-visas", "https://www.govt.nz/browse/immigration-and-visas/"],
}

TOPICS = {
    "renew": r"renew|extend|extension|renouvel|prolong|renova|pr[oó]rroga|verl[aä]nger|rinnov",
    "settle": r"settle|indefinite|permanent[- ]resid|\bpr[- ]card|long[- ]term|carte-de-resident|larga[- ]duraci|daueraufenthalt|niederlassung|lungo[- ]periodo|residencia-permanente|resid[eê]ncia-permanente",
    "citizenship": r"citizenship|naturali|nationalit[eéy]|einb[uü]rger|cittadinanza|nacionalidad|nacionalidade|become-a-citizen",
    "family": r"family|spouse|partner|dependant|dependent|reunif|regroupement|reagrupaci|nachzug|ricongiung|reagrupamento",
    "healthcare": r"health|medical|\bgp\b|\bnhs\b|sanidad|sant[eé]|assurance-maladie|krankenvers|sanitari|sa[uú]de|medisave|medicare",
    "taxid": r"national-insurance|social-insurance-number|\bsin\b|tax-number|tax-id|s[eé]curit[eé]-sociale|\bnie\b|\bnif\b|steuer|codice-fiscale|personnummer|ird-number|ppsn|numero-de-seguridad|n[uú]mero-de-identifica",
    "work_rights": r"employment-rights|rights-at-work|minimum-wage|working-hours|employment-standards|droit-du-travail|derechos-laborales|arbeitsrecht|diritti-dei-lavoratori|direitos-laborais|employment-act|holiday-entitlement",
    "driving": r"driv|permis-de-conduire|permiso-de-conducir|f[uü]hrerschein|patente|carta-de-condu|licen[cs]e-exchange",
    "housing": r"housing|renting|tenan|landlord|logement|vivienda|alquiler|wohnung|\bmiet|alloggio|habita[cç][aã]o|accommodation",
    "schooling": r"school|enrol|[eé]cole|scolarisation|escuela|escolariza|schule|scuola|escola",
    "integration": r"integrat|language-course|cours-de-fran|contrat-d-integration|integrationskurs|corsi-di-italiano|lingua",
    "complaints": r"discriminat|complain|ombudsman|defenseur-des-droits|defensor|beschwerde|reclamo|queixa|legal-aid|appeal",
}

UA_SKIP = re.compile(r"\.(pdf|jpg|png|zip|docx?)$|mailto:|javascript:|/search|/login|/print$", re.I)


def links(html: str, base: str) -> list[tuple[str, str]]:
    out = []
    for href, text in re.findall(r'<a\b[^>]*href="([^"#]+)"[^>]*>(.*?)</a>', html, re.I | re.S):
        u = urljoin(base, href.strip())
        if urlparse(u).netloc != urlparse(base).netloc or UA_SKIP.search(u):
            continue
        out.append((u.split("?")[0], re.sub(r"<[^>]+>|\s+", " ", text).strip()[:120]))
    return out


def main() -> int:
    only = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), "")
    countries = [c for c in HUBS if not only or c in only.upper().split(",")]
    f = Fetcher(delay_seconds=1.0)
    report = {}
    for code in countries:
        found: dict[str, list[tuple[str, str]]] = {t: [] for t in TOPICS}
        hubs_ok = []
        for hub in HUBS[code]:
            ok, why = f.allowed(hub)
            if not ok:
                print(f"{code} hub blocked by robots: {hub} ({why})", flush=True)
                continue
            r = f.fetch(hub)
            if r.outcome != "fetched":
                print(f"{code} hub {r.outcome} {r.status}: {hub}", flush=True)
                continue
            hubs_ok.append(hub)
            html = r.body.decode("utf-8", "replace")
            for u, text in links(html, r.final_url or hub):
                key = (u + " " + text).lower().replace(" ", "-")
                for topic, pat in TOPICS.items():
                    if re.search(pat, key) and u not in [x[0] for x in found[topic]]:
                        found[topic].append((u, text))
        report[code] = {"hubs": hubs_ok, "topics": {t: v[:6] for t, v in found.items()}}
        covered = sum(1 for v in found.values() if v)
        print(f"{code}: {len(hubs_ok)} hubs read, {covered}/{len(TOPICS)} topics have candidates", flush=True)
    json.dump(report, open("tools/living_candidates.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
