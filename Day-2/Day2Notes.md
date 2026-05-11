# Tutorial Notes for Students

These notes accompany the Day 2 tutorials. They are intended to help you understand what to expect before you begin the notebooks and what ideas you should be able to explain after working through them.

Day 2 focuses on using a Semantic Bridge workflow to move from unstructured documents to structured scientific and decision-relevant information. The work also introduces CKAN registration so that document corpora and derived outputs can be shared as reusable data products.

## What You Should Learn

By the end of the Day 2 tutorials, you should understand the following concepts:

- a document corpus is a collection of reports, transcripts, notes, PDFs, or other text sources used for analysis
- topic modeling helps identify recurring themes across a corpus
- a science backbone connects discovered themes to scientific domains and model-relevant terminology
- decision components describe goals, objectives, variables, constraints, and indicators found in the text
- scientific variable mappings help translate plain-language terms into measurable quantities
- CKAN registration makes corpora and outputs easier to discover, cite, and reuse

The main idea is that qualitative information can be organized into structures that support modeling, data discovery, and decision analysis.

## Begin With The Workflow

Before running the notebooks, it is helpful to understand the overall workflow. Day 2 is not just about running text-processing code. It is about building a bridge from narrative information to scientific and computational resources.

What to learn:

- where the input documents are located
- how the notebook loads and previews document text
- how topics are discovered from the corpus
- how those topics are mapped to scientific domains
- how decision components are extracted from the documents
- how variable mappings and output reports support later analysis

What to notice while working:

- whether the loaded documents are the ones you intended to analyze
- whether the discovered topics are meaningful or need refinement
- whether the extracted decision components match the problem context
- whether the scientific variable matches are specific enough to be useful
- what output files are created and where they are saved

## Document Corpus

The corpus is the input collection for the Semantic Bridge workflow.

What to learn:

- the workflow can use local tutorial documents or documents registered in CKAN
- supported inputs include text, JSON, Word documents, PDFs, and image files for OCR-based extraction
- clean text is preferred when available, but raw files can also be loaded
- previewing documents early helps catch missing files, poor extraction quality, or the wrong corpus

The corpus matters because every later step depends on the quality and relevance of the input documents.

## Topic Discovery

Topic discovery identifies major themes in the text.

What to learn:

- topic modeling groups words and phrases that commonly appear together
- model parameters control how many themes are discovered and how much vocabulary is considered
- topic labels and keywords are starting points for interpretation, not final answers
- filler words and repeated artifacts can distort the results if they are not removed

As you work through this section, focus on what each topic appears to mean in the context of the full corpus.

## Science Backbone And Variable Mapping

The science backbone connects narrative themes to scientific domains.

What to learn:

- discovered topics can be mapped to scientific domains using keywords, ETO exports, or MINT-based hints
- MINT and scientific-variable vocabularies provide a way to move from plain-language text toward measurable variables
- stricter matching reduces false positives, while looser matching may find more candidate variables
- visualizations such as networks and sunburst charts help summarize how the corpus connects to scientific concepts

The goal is not to let the notebook make final scientific judgments automatically. The goal is to produce organized candidates that can be reviewed and improved.

## Decision Components

Decision components identify the parts of a planning or management problem that appear in the corpus.

What to learn:

- goals describe what stakeholders or analysts are trying to achieve
- objectives are more specific aims
- decision variables are things that can be controlled or changed
- constraints describe limits on what is possible
- indicators describe how outcomes can be measured

This section is important because it connects text analysis to practical decision support.

## What The Semantic Bridge Notebook Demonstrates

[`Morning/semantic_bridge_cookbook.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-2/Morning/semantic_bridge_cookbook.ipynb) focuses on analysis.

Before you start:

- make sure the tutorial environment can import the `semantic_bridge` package and its notebook dependencies
- confirm that a document corpus is available locally or configured for CKAN download
- use the tutorial `.env` settings when you need CKAN, MINT, ETO, or LLM-assisted features

Expected outputs:

- topic, decision-component, and scientific-variable tables are written under `outputs/`
- interactive HTML figures such as the science-backbone network and SVO sunburst are generated
- a Markdown summary report and quick-reference table are created for review and handoff

As you work through it, pay attention to how the notebook:

- loads and inspects a document corpus
- removes filler words and prepares text for modeling
- discovers topics and summarizes their keywords
- builds science-domain mappings
- extracts decision components from the documents
- links narrative terms to scientific variables
- generates figures, tables, and a summary report

The main lesson is that unstructured documents can be processed into reusable scientific and decision-analysis products.

## What The CKAN Registration Notebook Demonstrates

[`Morning/semantic_bridge_ckan_registration_cookbook.ipynb`](https://github.com/In-For-Disaster-Analytics/DSO-Institute-2026/blob/main/Day-2/Morning/semantic_bridge_ckan_registration_cookbook.ipynb) focuses on publishing a document corpus.

Before you start:

- have a CKAN URL, credentials, and target owner organization ready
- configure the OpenAI-compatible LLM settings used to draft metadata
- make sure the selected corpus directory contains the PDFs you intend to publish

Expected outputs:

- a reviewed metadata plan is produced for the dataset and PDF resources
- a CKAN dataset is created or updated
- each selected PDF is uploaded as a CKAN resource with descriptive metadata

As you work through it, pay attention to how the notebook:

- loads CKAN, authentication, and LLM settings
- discovers PDFs in a corpus directory
- drafts resource metadata for each PDF
- lets you review or edit the upload plan
- proposes dataset-level metadata
- creates or updates a CKAN dataset
- uploads each PDF as a CKAN resource

The main lesson is that analysis inputs should be registered and described so they can be found, reused, and connected to downstream workflows.

## Recommended Order Of Study

To get the most from Day 2, use the following order:

1. Review the idea of a document corpus and confirm what files are being analyzed.
2. Run the Semantic Bridge notebook and focus first on the topic and decision-component outputs.
3. Review the variable mappings and figures to see how narrative text is connected to scientific concepts.
4. Inspect the generated report and output tables.
5. Run the CKAN registration notebook to understand how a corpus becomes a shareable dataset.
6. Compare the registered data products with the files used or produced by the analysis notebook.

## Main Takeaway

The most important idea to retain is that Day 2 turns narrative information into structured, shareable knowledge:

- the Semantic Bridge workflow organizes text into topics, decision components, scientific domains, and variable mappings
- CKAN registration makes the source corpus and related products discoverable and reusable

Together, these steps help connect stakeholder language, scientific terminology, and computational workflows.
