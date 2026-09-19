# Scholarly Standards Architecture & Resolution Hierarchy

Academic research happens in an international ecosystem where citation styles, metadata contracts, reporting guidelines, and provenance records must serve diverse disciplines and jurisdictions.

**Core Principle**: Natural language does not determine jurisdiction or citation standard. A researcher writing in Spanish may target an IEEE transaction; an author writing in English may need to satisfy a Chinese university's thesis format; a German medical paper must follow ICMJE and PRISMA.

## Resolution Hierarchy

When resolving citation, metadata, or reporting requirements, tools in this repository follow this strict priority chain:

```text
1. Target Venue or Funder Requirements
   (Journal author guidelines, conference style templates, thesis rules, grant agreements)
         ↓
2. Disciplinary Reporting Standards
   (PRISMA 2020 for systematic reviews, ICMJE for biomedical literature, CONSORT for trials)
         ↓
3. Applicable Regional or National Profiles
   (GB/T 7714-2025 in Mainland China, UNE-ISO 690:2024 in Spain, DIN ISO 690:2021 in Germany, etc.)
         ↓
4. International Baseline Standards
   (ISO 690:2021 for bibliographic references, W3C PROV for provenance, DataCite 4.7 for DOIs)
         ↓
5. Generic Style Fallback
   (Disciplinary defaults: APA 7th, IEEE, Chicago, ACM)
```

The machine-readable specification is maintained in `docs/standards/registry.json`.
