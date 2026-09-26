# Product Requirements Document (PRD)

## Project: Find the Missing Connections

**Version:** 1.0
**Date:** 26 September 2026
**Author:** TBD
**Status:** Draft
**Product:** Find the Missing Connections

---

# 1. Problem Statement

Knowledge articles contain references to people, places, and other articles. However, some referenced entities may not have their own article, and some article relationships may exist in only one direction.

The current problem is that these missing connections are difficult to identify manually.

The product will analyze an article, extract its people, places, and links, check whether corresponding articles exist, detect missing connections, detect one-way article links, and display the relationships as a connection map.

### Evidence

The source project definition identifies the required problem as:

* Finding people and places mentioned in articles that do not have their own article.
* Finding article connections that exist only in one direction.
* Mapping these relationships.
* Highlighting missing connections.

### Problem to solve

> Given an article, identify its relevant people, places, and article links, determine which connections have an existing article, identify missing connections, identify one-way article links, and visually map the results.

---

# 2. Goals

## 2.1 Product Goals

**G-01:** Allow a user to enter an article name.

**G-02:** Retrieve the requested article from Wikipedia/MediaWiki.

**G-03:** Extract people, places, and article links from the article.

**G-04:** Check whether each linked entity/article exists.

**G-05:** Identify missing connections.

**G-06:** Detect one-way connections between articles.

**G-07:** Build a connection map representing the discovered relationships.

**G-08:** Clearly highlight missing connections.

These goals follow the defined core project scope.

---

# 3. Non-Goals

The following are explicitly outside the scope of Version 1.0:

**NG-01:** Retrieval-Augmented Generation (RAG).

**NG-02:** Semantic search.

**NG-03:** AI research assistant.

**NG-04:** Article recommendation engine.

**NG-05:** Topic classification.

**NG-06:** Educational learning assistant.

**NG-07:** Knowledge-gap scoring or priority scoring.

**NG-08:** Connection-path finder.

**NG-09:** AI-generated explanations of relationships.

**NG-10:** Full Wikipedia mirroring.

**NG-11:** Large-scale storage of millions of articles or embeddings.

The source explicitly states that unrelated functionality should not be added to the core project.

---

# 4. Target Users

## Primary User

A user who wants to investigate relationships between entities and articles.

### User needs

The user needs to:

* Search for an article.
* Understand which people and places are connected to it.
* Identify missing articles.
* Identify one-way article connections.
* See the relationships visually.

The source defines the product around a user providing an article and the system analyzing its content.

---

# 5. User Stories

### US-01 — Search Article

> As a user, I want to enter an article name, so that I can analyze its connections.

### US-02 — View Extracted Entities

> As a user, I want to see the people and places extracted from an article, so that I can understand its referenced entities.

### US-03 — Identify Existing Articles

> As a user, I want the system to check whether an entity has its own article, so that I can distinguish valid connections from missing ones.

### US-04 — Find Missing Connections

> As a user, I want to see entities that do not have an article, so that I can identify missing connections.

### US-05 — Find One-Way Connections

> As a user, I want to know when Article A links to Article B but Article B does not link back, so that I can identify one-way connections.

### US-06 — View Connection Map

> As a user, I want to see the relationships between articles and entities as a map, so that I can understand the connection structure visually.

---

# 6. Functional Requirements

## 6.1 Article Search

### FR-01

The system shall provide an input field for an article name.

**Acceptance Criteria:**

* User can enter an article name.
* User can submit the article for analysis.

### FR-02

The system shall search for the requested article using the Wikipedia/MediaWiki API.

**Acceptance Criteria:**

* A valid article name returns the corresponding article.
* An unavailable article produces an appropriate error state.

---

## 6.2 Article Retrieval

### FR-03

The system shall retrieve the article title.

### FR-04

The system shall retrieve the article URL.

### FR-05

The system shall retrieve the article content required for connection analysis.

**Acceptance Criteria:**

* Article title is available to the analysis process.
* Article URL is available.
* Article content is available before extraction starts.

The source defines the article data as title, content, and links.

---

## 6.3 Entity Extraction

### FR-06

The system shall extract people mentioned in the article.

### FR-07

The system shall extract places mentioned in the article.

### FR-08

The system shall extract article links appearing in the article.

**Acceptance Criteria:**

* Extracted people are displayed under People.
* Extracted places are displayed under Places.
* Extracted article links are displayed under Links.

The source explicitly identifies people, places, and links as the required extracted information.

---

## 6.4 Article Existence Check

### FR-09

The system shall check whether an extracted entity has its own article.

### FR-10

The system shall classify an entity with an existing article as an existing connection.

### FR-11

The system shall classify an entity without an article as a missing connection.

**Acceptance Criteria:**

| Condition              | Result  |
| ---------------------- | ------- |
| Article exists         | EXISTS  |
| Article does not exist | MISSING |

This exists/missing classification is explicitly defined in the source.

---

## 6.5 Missing Connections

### FR-12

The system shall display all identified missing connections.

### FR-13

The system shall display the name of each missing entity.

### FR-14

The system shall display the entity type for each missing entity.

Supported entity types in the source are:

* Person
* Place

**Acceptance Criteria:**

* Missing entities appear in the Missing Connections section.
* Each entity has a name.
* Each entity is identified as a person or place where available.

---

## 6.6 One-Way Connections

### FR-15

The system shall check whether an article linking to another article has a reverse link.

### FR-16

The system shall classify a connection as one-way when Article A links to Article B and Article B does not link to Article A.

### FR-17

The system shall display one-way connections separately.

**Acceptance Criteria:**

Given:

`Article A → Article B`

and:

`Article B → Article A = false`

the system shall classify the relationship as:

`ONE-WAY`

The source explicitly defines this reverse-link check.

---

## 6.7 Connection Map

### FR-18

The system shall generate a connection map for the analyzed article.

### FR-19

The map shall represent the analyzed article as a node.

### FR-20

The map shall represent connected people as nodes.

### FR-21

The map shall represent connected places as nodes.

### FR-22

The map shall represent connected articles as nodes.

### FR-23

The map shall visually distinguish missing connections.

**Acceptance Criteria:**

* The analyzed article appears in the map.
* Connected entities appear as related nodes.
* Missing entities are visually identifiable.
* Relationships are represented as edges.

The source defines the connection map around Article → Person, Place, Article, and Missing Connection relationships.

---

## 6.8 Result Summary

### FR-24

The system shall display the total number of connections found.

### FR-25

The system shall display the number of existing articles.

### FR-26

The system shall display the number of missing connections.

### FR-27

The system shall display the number of one-way connections.

The source defines these four result categories.

---

# 7. Non-Functional Requirements

## 7.1 Performance

### NFR-01

The system shall not make duplicate article requests when the required article data is already available in the application cache.

### NFR-02

The system shall reuse previously retrieved article data where applicable.

The source specifies caching to avoid repeatedly calling Wikipedia.

**Response-time target:** TBD.

---

## 7.2 Reliability

### NFR-03

The system shall handle unavailable article responses without crashing.

### NFR-04

The system shall handle failed external API requests with an error state.

### NFR-05

The system shall not treat an API failure as evidence that an article is missing.

---

## 7.3 Security

### NFR-06

The backend shall validate user input before processing it.

### NFR-07

The backend shall apply API request timeouts.

### NFR-08

The backend shall implement rate limiting.

### NFR-09

The backend shall not allow users to submit arbitrary URLs for server-side fetching.

The source specifically identifies input validation, rate limiting, API timeouts, and SSRF prevention as security requirements.

---

## 7.4 Data Integrity

### NFR-10

Each stored link shall reference a source article and a target article.

### NFR-11

Each missing connection shall reference its source article, entity name, and entity type.

---

## 7.5 Accessibility

### NFR-12

The required accessibility target is **TBD**.

No specific accessibility standard or target is defined in the source material.

---

# 8. Data Model

Only data required for the core project shall be stored.

## Articles

| Field | Description        |
| ----- | ------------------ |
| id    | Article identifier |
| title | Article title      |
| url   | Article URL        |

## Links

| Field          | Description     |
| -------------- | --------------- |
| id             | Link identifier |
| source_article | Source article  |
| target_article | Target article  |

## Missing Connections

| Field          | Description                       |
| -------------- | --------------------------------- |
| id             | Missing connection identifier     |
| source_article | Article containing the connection |
| entity_name    | Missing person/place name         |
| entity_type    | Person or Place                   |

This follows the source's defined database scope.

---

# 9. Technology Requirements

The source specifies the following free implementation stack:

| Layer          | Technology                |
| -------------- | ------------------------- |
| Frontend       | React                     |
| Backend        | Python + FastAPI          |
| Article Source | Wikipedia / MediaWiki API |
| Database       | PostgreSQL                |
| Connection Map | Cytoscape.js              |

No paid API is required for the defined implementation.

---

# 10. UX / Screen Requirements

## Screen 1 — Search Page

The page shall contain:

* Product/project title: **Find the Missing Connections**
* Article name input
* Analyze button

Flow:

`Enter article name → Analyze`

---

## Screen 2 — Article Analysis

The page shall display:

* Article Name
* People
* Places
* Links

These are the required analysis outputs defined in the source.

---

## Screen 3 — Missing Connections

The page shall display:

**Missing Connections**

Example:

1. Person X
2. Place Y
3. Person Z

Only entities identified as missing shall appear in this section.

---

## Screen 4 — Connection Map

The page shall display:

```text
                 Article
                /   |   \
               /    |    \
          Person  Place  Article
             ✓      ✓      ✓
                    |
                    ▼
               Person X
                MISSING
```

The visual implementation shall use Cytoscape.js.

---

## Screen 5 — One-Way Connections

The page shall display:

**One-Way Connections**

Example:

```text
Article A → Article B
```

The reverse connection shall be identified as missing.

---

# 11. End-to-End User Flow

```text
User
  ↓
Enter Article
  ↓
Search Article
  ↓
Get Article Content
  ↓
Extract Names + Links
  ↓
Check Each Link
  ↓
 ┌─────────────────────┐
 │                     │
 ▼                     ▼
Article Exists     Article Missing
 │                     │
 ▼                     ▼
Valid Connection   Missing Connection
 │                     │
 └──────────┬──────────┘
            ▼
    Check Reverse Links
            │
            ▼
    Build Connection Map
            │
            ▼
    Highlight Missing
```

This follows the source-defined system flow.

---

# 12. Edge Cases & Error Handling

## EC-01 — Article Not Found

**Condition:** Requested article cannot be found.

**Expected behavior:** Display an article-not-found error and do not begin connection analysis.

---

## EC-02 — Empty Input

**Condition:** User submits an empty article name.

**Expected behavior:** Do not send the request and display an input validation message.

---

## EC-03 — Wikipedia API Failure

**Condition:** Wikipedia/MediaWiki API request fails.

**Expected behavior:** Display an API error and do not classify the affected article as missing.

---

## EC-04 — Article Has No Relevant Links

**Condition:** Article contains no links relevant to the analysis.

**Expected behavior:** Display zero connections and an empty connection-map state.

---

## EC-05 — Missing Entity

**Condition:** A referenced person/place has no corresponding article.

**Expected behavior:** Mark the entity as `MISSING`.

---

## EC-06 — One-Way Link

**Condition:** Article A links to Article B but Article B does not link to Article A.

**Expected behavior:** Mark the relationship as `ONE-WAY`.

---

## EC-07 — Duplicate Connection

**Condition:** The same connection is encountered more than once during analysis.

**Expected behavior:** Store/display one logical connection rather than duplicate results.

---

# 13. Success Metrics / KPIs

The source does not provide numerical product-performance targets, so targets must not be invented at PRD stage.

## Product Metrics

| Metric                                 | Baseline | Target |
| -------------------------------------- | -------: | -----: |
| Articles successfully analyzed         |      TBD |    TBD |
| Connections detected correctly         |      TBD |    TBD |
| Missing connections detected correctly |      TBD |    TBD |
| One-way connections detected correctly |      TBD |    TBD |
| Article retrieval success rate         |      TBD |    TBD |
| API error rate                         |      TBD |    TBD |

### Required before Approval

The product owner/stakeholders must define the numerical targets and measurement method before the PRD is marked **Approved**.

---

# 14. Assumptions

**A-01:** Wikipedia/MediaWiki API will be the article source.

**A-02:** Article links can be obtained through the MediaWiki API.

**A-03:** Article existence can be determined using the article source.

**A-04:** The initial product analyzes an article selected by the user rather than mirroring all of Wikipedia.

**A-05:** PostgreSQL is sufficient for storing the required core data.

**A-06:** Cytoscape.js will be used to visualize the connection map.

These assumptions are based on the implementation defined in the source.

---

# 15. Dependencies

| Dependency                | Purpose                      |
| ------------------------- | ---------------------------- |
| Wikipedia / MediaWiki API | Article and link data        |
| React                     | Frontend                     |
| FastAPI                   | Backend API                  |
| Python                    | Backend implementation       |
| PostgreSQL                | Data storage                 |
| Cytoscape.js              | Connection-map visualization |

---

# 16. Risks

## R-01 — External API Availability

The application depends on the availability of the Wikipedia/MediaWiki API.

**Mitigation:** Handle API errors and use caching.

---

## R-02 — API Request Volume

Repeated article requests may create unnecessary external API traffic.

**Mitigation:** Cache retrieved article data.

The source explicitly recommends caching to avoid repeated Wikipedia calls.

---

## R-03 — Incorrect Entity Classification

Names extracted from article content may not always be correctly identified as people or places.

**Mitigation:** Keep extraction logic separate from connection verification and validate results during testing.

---

## R-04 — SSRF Risk

Allowing arbitrary user-supplied URLs could cause unsafe server-side requests.

**Mitigation:** The backend shall use the defined article source/API rather than accepting arbitrary URLs.

This security concern is explicitly identified in the source.

---

# 17. Rollout Plan

## Phase 1 — Article Search

Deliver:

* Article input
* Article search
* Article retrieval

**Exit Criteria:** User can enter an article and retrieve its basic data.

---

## Phase 2 — Connection Detection

Deliver:

* People extraction
* Place extraction
* Link extraction
* Article existence checking
* Missing connection detection

**Exit Criteria:** The system can distinguish existing and missing connections.

---

## Phase 3 — One-Way Connections

Deliver:

* Reverse-link checking
* One-way connection detection

**Exit Criteria:** Article A → Article B without B → A is correctly identified.

---

## Phase 4 — Connection Map

Deliver:

* Article nodes
* Person nodes
* Place nodes
* Article nodes
* Missing connection nodes
* Relationship edges
* Missing-state highlighting

**Exit Criteria:** The analyzed article's relationships are visually represented.

---

## Phase 5 — Testing & Deployment

Deliver:

* Functional testing
* Edge-case testing
* API failure testing
* Security testing
* Production deployment

**Exit Criteria:** All approved functional requirements pass their acceptance criteria.

---

# 18. Release Scope

## Version 1.0 MUST contain

* Article search
* Article retrieval
* People extraction
* Place extraction
* Link extraction
* Article existence checking
* Missing connection detection
* One-way connection detection
* Connection map
* Missing connection highlighting
* Required result counts

## Version 1.0 MUST NOT contain

* RAG
* Semantic search
* AI research assistant
* Article recommendations
* Topic classification
* Educational assistant
* Scoring
* Connection-path finder
* AI-generated relationship explanations

---

# 19. Acceptance Criteria — MVP

The MVP is considered complete only when all of the following are true:

* [ ] User can enter an article name.
* [ ] System can retrieve the requested article.
* [ ] System can extract people.
* [ ] System can extract places.
* [ ] System can extract article links.
* [ ] System can determine whether a referenced article exists.
* [ ] System marks nonexistent articles/entities as `MISSING`.
* [ ] System checks reverse article links.
* [ ] System marks non-reciprocal links as `ONE-WAY`.
* [ ] System displays missing connections.
* [ ] System displays one-way connections.
* [ ] System generates a connection map.
* [ ] Missing connections are visually distinguishable.
* [ ] System handles article/API errors without crashing.
* [ ] Required data is stored in PostgreSQL.
* [ ] No out-of-scope feature is required for MVP approval.

The source identifies the core MVP around search, Wikipedia API integration, extraction, missing-link detection, existing-link detection, one-way detection, PostgreSQL, basic graph, and the required interface.

---

# 20. Open Questions

These items are not specified by the source and must be resolved before final approval:

**OQ-01:** What exact response-time target should be used for article analysis?

**OQ-02:** What exact accuracy target should be used for person/place extraction?

**OQ-03:** What exact accuracy target should be used for missing-connection detection?

**OQ-04:** What accessibility standard should the application target?

**OQ-05:** What authentication requirement, if any, is required for the first release?

**OQ-06:** What maximum number of connections should be displayed in the first map view?

**OQ-07:** What exact behavior should occur when an entity has redirects or alternate article titles?

These questions are intentionally left open because the source does not define their answers.

---

# 21. Revision History

| Version | Date        | Author | Status | Changes     |
| ------- | ----------- | ------ | ------ | ----------- |
| 1.0     | 26 Sep 2026 | TBD    | Draft  | Initial PRD |

---

# 22. Approval

| Stakeholder | Role           | Status  | Date |
| ----------- | -------------- | ------- | ---- |
| TBD         | Product Owner  | Pending | TBD  |
| TBD         | Technical Lead | Pending | TBD  |
| TBD         | Design/UX      | Pending | TBD  |

**Implementation shall begin after the PRD is approved.**

After implementation, the document may be updated to reflect the final as-built behavior.
