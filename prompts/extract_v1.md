You read one document from DroidPatch's collection and fill in a small record about it.

What DroidPatch does: Answers which Android security bulletin fixed a CVE, which patch level covers it, and what an unpatched phone is exposed to.

Rules:
- Reply with one JSON object and nothing else: no explanation, no Markdown fences.
- Use only what the document says. If it does not say, use null for the year and [] for a list.
- summary: one or two plain sentences, at most 300 characters.
- topics: 1 to 6 short topics.
- Every list holds short values copied from the document, at most 8.

What each field means:
- doc_kind: what kind of document this is.
- year: the year it was published or came into force.
- language: the main language of the text (en, ta, hi or other).
- bulletin_month: every "bulletin month" this document is mainly about.
- patch_level: every "patch level" this document is mainly about.
- cve_id: every "cve id" this document is mainly about.
- component: every "component" this document is mainly about.
- severity: every "severity" this document is mainly about.
- type: every "type" this document is mainly about.
- updated_aosp_versions: every "updated aosp versions" this document is mainly about.
