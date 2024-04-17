# What Are ADRs?

Architecture Decision Records (ADRs) are a structured way to document significant decisions made during the design and 
evolution of a software system or an architectural component. These records capture the context, rationale, and 
consequences of each decision. Here’s what you need to know:

ADRs serve as a historical record, allowing engineers to understand why certain architectural choices were made. By 
documenting decisions, ADRs prevent recurring debates and provide clarity.

## Benefits of ADRs

- **Transparency:** ADRs make architectural decisions visible and accessible.
- **Traceability:** Teams can trace back to the reasoning behind a specific choice.
- **Consistency:** Encourages consistent decision-making across projects.
- **Learning:** ADRs help new engineers understand the system’s evolution.

## How to add an ADR

Create a new file in the format `yyyy-mm-dd-<title>.md` in this directory. Copy in the template from `template.md` and
fill in the relevant details. Once complete, raise a PR and discuss your proposal with other engineers involved in the 
project.

Unless in a draft state, once merged, ADRs should be immutable *except* for the status. If an ADR needs to be changed,
create a new ADR with the reasoning and change the existing ADR status to `superseeded - <link to new ADR>`.