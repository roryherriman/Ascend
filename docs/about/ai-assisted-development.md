# AI-Assisted Development Disclosure

Ascend was built with significant use of AI tools, primarily Claude (Anthropic). This document explains what that means, what it does not mean, and why the creator believes it is worth disclosing.

## What "AI-assisted" means here

AI tools were used extensively throughout development:

- **Code generation** — significant portions of the codebase were written with AI assistance, including drafts of UI components, data models, migration logic, test cases, and architecture documents
- **Iteration and debugging** — AI was used to reason through errors, explore design alternatives, and refine implementations
- **Documentation** — some documentation was drafted collaboratively with AI tools and then reviewed and edited by the creator

This is not a case of AI generating a small utility function or autocompleting a line. The creator acknowledges that AI assistance was material to the scope and pace of this project.

## What "AI-assisted" does not mean

- The creator does not understand the code less because AI helped write it. Every piece that ships was reviewed, adjusted, and approved by a human who is responsible for it.
- AI did not make product decisions. Feature scope, architecture, design tradeoffs, and priorities were decided by the creator.
- AI did not review or validate the code independently. AI suggestions can be wrong. The creator caught and fixed errors during review.
- The use of AI tools does not reduce accountability. If Ascend has a bug, a security issue, or a bad design decision, that is the creator's responsibility — not the tool's.

## Why this is disclosed

Most software built with AI assistance does not say so. The creator believes that's a mistake, especially for a tool that handles user credentials, reads personal performance data, and makes claims about privacy and security.

If you are evaluating whether to trust this software, you should know how it was built. That means knowing AI tools were involved, knowing the creator is not a career software engineer, and knowing the creator takes responsibility for the result anyway.

This disclosure is also permanent. Future updates will continue to be built with AI assistance. The framing — human-directed, AI-assisted — is the honest description of how this project works.

## Development approach

The creator describes the process as **human-directed, AI-assisted**:

- The creator sets direction, defines requirements, and makes final decisions
- AI tools generate candidate implementations, documentation, and analysis
- The creator reviews, tests, and modifies before anything ships
- Responsibility for the product remains with the creator entirely

This is consistent with how a senior engineer uses junior contributors, or how an architect uses a contractor: the judgment, accountability, and final authority stay with the person who owns the product.

## Verifiability

The source code for Ascend is publicly available at the GitHub repository linked from this project. The commit history, test suite, and architecture documents are all visible. Anyone who wants to audit the code can do so.

AI-generated code is not distinguishable from human-written code by inspection. What is distinguishable is whether the code is correct, tested, and well-structured. That is where trust should be evaluated — not on the basis of who or what typed the characters.
