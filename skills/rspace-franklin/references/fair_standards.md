# FAIR standards for this lab

*[EDIT ME]* This entire file is a placeholder. Replace the example below with the actual standards, persistent identifier schemes, and ontologies your lab or institution uses, so the assistant applies your conventions rather than guessing.

---

## Example (replace this)

**Persistent identifiers**

- Samples: Use RSpace Global IDs as the internal reference; additionally mint a DOI via [your repository] only when the sample should be published. 

**Ontologies / controlled vocabularies**

- Experimental techniques: tag using [EDAM](https://edamontology.org) terms where applicable.
- Organisms: use NCBI Taxonomy IDs alongside the common name.

**Metadata minimums**

- Every dataset document should record: instrument or method, date (ISO 8601), operator, and a link to the related protocol or SOP.

**Data structures**

Structure experiments using the ISA (Investigation-Study-Assay) model:

- **Investigation** — the overall research project or aim. Represent this as a top-level RSpace Folder, one per project.
- **Study** — a coherent set of experiments addressing one research question within the investigation, with its own design and subjects/samples. Represent as a sub-folder under the Investigation, carrying the study design metadata (objective, factors, subjects) as a document.
- **Assay** — a single measurement or protocol run within a study (e.g. one sequencing run, one set of qPCR measurements), with samples linked via the list of materials. Represent as individual document or notebook in the Study folder, tagged with the assay/measurement type.

*Worked example:* Investigation folder "Circadian gene expression in zebrafish" contains a Study sub-folder "Light-cycle entrainment, cohort 3", which contains Assay documents such as "qPCR — per2 expression, day 1" and "qPCR — per2 expression, day 4".

**Licensing**

- Default new shared datasets to CC-BY 4.0 unless a specific project requires otherwise.
