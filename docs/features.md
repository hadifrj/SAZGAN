# Features

This document contains the stable functional specifications kept with the source. It is organized by capability rather than by development stage or release batch.

## Customers

## Scope
 introduces the Customers information architecture and UI foundation.

## Workflow guarantee
The existing operational workflow is not changed.

No existing:
- chat status flow
- reply/quote flow
- ticket flow
- follow-up flow
- service flow

is altered by .

## Data guarantee
No new database table or migration is required by the  UI foundation.

The page is designed to consume the project's existing customer records and existing customer-related relationships.

## Customer profile
The intended profile sections are:
- Customer identity
- Contact details
- Conversations
- Tickets
- Follow-ups
- Services
- Products / warranty
- Surveys
- Internal notes

## Navigation
The Customers page is intended to be reachable from:
- Main navigation
- Dashboard customer card / customer count
- Global search in a later release

## Search
The page supports the UX concept of searching by:
- Name
- Phone
- Email
- Customer ID

## Next implementation step
Connect the UI to the project's existing customer query/route after confirming the current customer model and route names. This avoids inventing a second customer data source.

## Tickets

## Scope
Add the Tickets page and information architecture.

## Workflow guarantee
The existing application workflow remains unchanged.  does not redefine chat, reply, quote, follow-up, service, or customer flows.

## Ticket lifecycle
The UI supports these operational states:
- Open
- Waiting for Customer
- Waiting for Support
- Resolved
- Closed

Priority:
- Urgent
- High
- Normal
- Low

## Ticket detail
The intended detail view contains:
- Ticket ID
- Customer
- Subject
- Priority
- Assignee
- Status
- Created / updated timestamps
- Conversation
- Attachments
- Internal notes
- Activity history

## Data policy
No new database table or migration is introduced by this UI foundation. The eventual implementation should reuse an existing ticket/request model if one exists rather than creating duplicate data.

## Integration points
Tickets should be reachable from:
- Main navigation
- Customer profile
- Dashboard
- A later global search

## Safety
Do not automatically convert existing conversations into tickets without an explicit business rule and approval.

## Follow-ups

## Scope
Add a dedicated Follow-ups page for scheduled customer actions.

## Workflow guarantee
The existing workflow is unchanged. This release does not alter Chat, Reply, Quote, Ticket, Customer, or Service behavior.

## Filters
- Today
- Overdue
- Tomorrow
- This Week
- Completed
- All

## Follow-up fields
The UI is designed for:
- Follow-up ID
- Customer
- Task / action
- Due date and time
- Assignee
- Priority
- Status
- Related conversation / ticket / service
- Notes
- Completion timestamp

## Design principle
A follow-up should be an explicit action attached to an existing business object. It should not silently change the status of a conversation or ticket.

## Data policy
No new database table or migration is introduced by this UI foundation. Reuse an existing follow-up/task model if present; otherwise define the schema only after approval.

## Safety
Creating a follow-up must not automatically close, archive, resolve, or reopen a conversation or ticket unless a later business rule explicitly defines that behavior.

## Products and warranty

## Scope
Add the Products & Warranty information architecture.

## Product profile
The intended record contains:
- Product
- Model
- Serial number
- Customer
- Purchase date
- Warranty start
- Warranty end
- Warranty status
- Product status
- Service history

## Warranty views
- Active
- Expiring Soon
- Expired
- No Warranty

## Search
Search by:
- Product
- Model
- Serial number
- Customer

## Workflow guarantee
No Chat, Ticket, Follow-up, Service, Customer or Survey workflow is changed.

## Data policy
This is an additive UI foundation. No database migration or new table is introduced in this release.
Existing product/warranty data should be reused when available.

## Safety
Adding a product or changing warranty information must not automatically close, resolve, archive or reopen a support workflow.

## Combined product and survey changes

This package combines:
-  Products & Warranty
-  Customer Surveys

The releases are grouped only for testing convenience.

## Unchanged
- Existing workflow
- Chat / Reply / Quote
- Ticket lifecycle
- Follow-up lifecycle
- Customer workflow
- Database schema
- Migration requirements

## Important
Products/Warranty and Surveys are additive UI foundations. They do not silently create a second data source or modify existing workflow states.

## Surveys

## Scope
Add the Customer Surveys / Satisfaction page.

## Workflow guarantee
Existing Chat, Reply, Quote, Customer, Ticket, Follow-up and Service workflows remain unchanged.

## Views
- All Responses
- Positive
- Neutral
- Negative
- Pending

## Summary
- Satisfaction percentage
- Total responses
- Positive responses
- Negative responses

## Filters
- Search
- Period
- Survey type

## Survey types
- Service
- Support
- Product

## Intended response detail
- Customer
- Survey type
- Score / rating
- Submitted date
- Related conversation / ticket / service
- Comment / feedback
- Assigned follow-up when applicable

## Data policy
This UI foundation introduces no database table and no migration. Existing survey/feedback data should be reused when present.

## Business rule
Negative feedback must not automatically close, reopen, resolve, archive, or otherwise change another workflow object unless an explicit rule is approved later.

## Reports

## Scope
Add the Reports information architecture and reporting UI.

## Report groups
- Overview
- Customer Service
- Support
- Technicians
- Customer Satisfaction

## KPIs
- Conversations
- Tickets
- Average response time
- Average resolution time
- Services
- Satisfaction

## Periods
- Last 7 days
- Last 30 days
- Last 90 days
- Last 12 months

## Export
The UI provides entry points for:
- CSV export
- Report export

The actual export implementation should use existing application data sources and approved export libraries.

## Workflow guarantee
No operational workflow is changed by this release. Reports are read-only and must not mutate Chat, Ticket, Follow-up, Customer, Service, Product or Survey records.

## Data policy
No new database table or migration is introduced by this UI foundation.

## Global search

## Scope
Add one search entry point for the major operational records.

## Search targets
- Customers
- Conversations
- Tickets
- Products
- Services
- Surveys

## Search keys
Depending on the record type:
- Customer name
- Phone
- Email
- Customer ID
- Ticket ID
- Ticket subject
- Serial number
- Product/model
- Service ID
- Survey/customer text

## UX
- One search box
- Category tabs
- Result count
- Clear action
- Result preview
- Result navigation to the original record

## Workflow guarantee
Search is read-only. Selecting a result must not change:
- Chat status
- Ticket status
- Follow-up status
- Customer status
- Service status
- Warranty status
- Survey status

## Data policy
No new database table or migration is introduced by this UI foundation.
Search should reuse existing application data sources.

## Performance principle
The eventual backend implementation should use indexed, scoped queries rather than loading every record into memory.

## Security principle
Search results must respect the current user's permissions and must not expose records the user cannot already access.

## Roles and permissions

## Scope
Add the Roles & Permissions information architecture.

## Principle
Permissions must be enforced server-side. The UI checkboxes are only the administration interface and are not a security boundary.

## Permission groups
- Customers
- Conversations
- Tickets
- Follow-ups
- Products & Warranty
- Surveys
- Reports
- Administration

## Permission actions
Examples:
- View
- Create
- Edit
- Delete
- Reply
- Archive
- Manage
- Complete
- Export

## Security rules
1. Existing administrator access must not be removed automatically.
2. A user must never gain access merely because a button is hidden/shown.
3. Server-side authorization must protect every protected route/action.
4. Global Search must return only records the current user is authorized to see.
5. Reports export requires explicit export permission.
6. Role changes should be audited.

## Workflow guarantee
Adding permissions does not change the operational workflow. It only controls who may perform existing actions.

## Data policy
This UI foundation adds no database migration. The final backend integration must reuse the existing user/role model if present.


## Disconnected feature notes

# Reference: disconnected feature notes

## .md

# SAZGAN  — Customers

## Scope
 introduces the Customers information architecture and UI foundation.

## Workflow guarantee
The existing operational workflow is not changed.

No existing:
- chat status flow
- reply/quote flow
- ticket flow
- follow-up flow
- service flow

is altered by .

## Data guarantee
No new database table or migration is required by the  UI foundation.

The page is designed to consume the project's existing customer records and existing customer-related relationships.

## Customer profile
The intended profile sections are:
- Customer identity
- Contact details
- Conversations
- Tickets
- Follow-ups
- Services
- Products / warranty
- Surveys
- Internal notes

## Navigation
The Customers page is intended to be reachable from:
- Main navigation
- Dashboard customer card / customer count
- Global search in a later release

## Search
The page supports the UX concept of searching by:
- Name
- Phone
- Email
- Customer ID

## Next implementation step
Connect the UI to the project's existing customer query/route after confirming the current customer model and route names. This avoids inventing a second customer data source.

## .md

# SAZGAN  — Tickets

## Scope
Add the Tickets page and information architecture.

## Workflow guarantee
The existing application workflow remains unchanged.  does not redefine chat, reply, quote, follow-up, service, or customer flows.

## Ticket lifecycle
The UI supports these operational states:
- Open
- Waiting for Customer
- Waiting for Support
- Resolved
- Closed

Priority:
- Urgent
- High
- Normal
- Low

## Ticket detail
The intended detail view contains:
- Ticket ID
- Customer
- Subject
- Priority
- Assignee
- Status
- Created / updated timestamps
- Conversation
- Attachments
- Internal notes
- Activity history

## Data policy
No new database table or migration is introduced by this UI foundation. The eventual implementation should reuse an existing ticket/request model if one exists rather than creating duplicate data.

## Integration points
Tickets should be reachable from:
- Main navigation
- Customer profile
- Dashboard
- A later global search

## Safety
Do not automatically convert existing conversations into tickets without an explicit business rule and approval.

## .md

# SAZGAN  — Follow-ups

## Scope
Add a dedicated Follow-ups page for scheduled customer actions.

## Workflow guarantee
The existing workflow is unchanged. This release does not alter Chat, Reply, Quote, Ticket, Customer, or Service behavior.

## Filters
- Today
- Overdue
- Tomorrow
- This Week
- Completed
- All

## Follow-up fields
The UI is designed for:
- Follow-up ID
- Customer
- Task / action
- Due date and time
- Assignee
- Priority
- Status
- Related conversation / ticket / service
- Notes
- Completion timestamp

## Design principle
A follow-up should be an explicit action attached to an existing business object. It should not silently change the status of a conversation or ticket.

## Data policy
No new database table or migration is introduced by this UI foundation. Reuse an existing follow-up/task model if present; otherwise define the schema only after approval.

## Safety
Creating a follow-up must not automatically close, archive, resolve, or reopen a conversation or ticket unless a later business rule explicitly defines that behavior.

## .md

# SAZGAN  — Products & Warranty

## Scope
Add the Products & Warranty information architecture.

## Product profile
The intended record contains:
- Product
- Model
- Serial number
- Customer
- Purchase date
- Warranty start
- Warranty end
- Warranty status
- Product status
- Service history

## Warranty views
- Active
- Expiring Soon
- Expired
- No Warranty

## Search
Search by:
- Product
- Model
- Serial number
- Customer

## Workflow guarantee
No Chat, Ticket, Follow-up, Service, Customer or Survey workflow is changed.

## Data policy
This is an additive UI foundation. No database migration or new table is introduced in this release.
Existing product/warranty data should be reused when available.

## Safety
Adding a product or changing warranty information must not automatically close, resolve, archive or reopen a support workflow.

## .6_COMBINED_RELEASE.md

# SAZGAN  +  Combined Test Release

This package combines:
-  Products & Warranty
-  Customer Surveys

The releases are grouped only for testing convenience.

## Unchanged
- Existing workflow
- Chat / Reply / Quote
- Ticket lifecycle
- Follow-up lifecycle
- Customer workflow
- Database schema
- Migration requirements

## Important
Products/Warranty and Surveys are additive UI foundations. They do not silently create a second data source or modify existing workflow states.

## .md

# SAZGAN  — Surveys

## Scope
Add the Customer Surveys / Satisfaction page.

## Workflow guarantee
Existing Chat, Reply, Quote, Customer, Ticket, Follow-up and Service workflows remain unchanged.

## Views
- All Responses
- Positive
- Neutral
- Negative
- Pending

## Summary
- Satisfaction percentage
- Total responses
- Positive responses
- Negative responses

## Filters
- Search
- Period
- Survey type

## Survey types
- Service
- Support
- Product

## Intended response detail
- Customer
- Survey type
- Score / rating
- Submitted date
- Related conversation / ticket / service
- Comment / feedback
- Assigned follow-up when applicable

## Data policy
This UI foundation introduces no database table and no migration. Existing survey/feedback data should be reused when present.

## Business rule
Negative feedback must not automatically close, reopen, resolve, archive, or otherwise change another workflow object unless an explicit rule is approved later.

## .md

# SAZGAN  — Reports

## Scope
Add the Reports information architecture and reporting UI.

## Report groups
- Overview
- Customer Service
- Support
- Technicians
- Customer Satisfaction

## KPIs
- Conversations
- Tickets
- Average response time
- Average resolution time
- Services
- Satisfaction

## Periods
- Last 7 days
- Last 30 days
- Last 90 days
- Last 12 months

## Export
The UI provides entry points for:
- CSV export
- Report export

The actual export implementation should use existing application data sources and approved export libraries.

## Workflow guarantee
No operational workflow is changed by this release. Reports are read-only and must not mutate Chat, Ticket, Follow-up, Customer, Service, Product or Survey records.

## Data policy
No new database table or migration is introduced by this UI foundation.

## .md

# SAZGAN  — Global Search

## Scope
Add one search entry point for the major operational records.

## Search targets
- Customers
- Conversations
- Tickets
- Products
- Services
- Surveys

## Search keys
Depending on the record type:
- Customer name
- Phone
- Email
- Customer ID
- Ticket ID
- Ticket subject
- Serial number
- Product/model
- Service ID
- Survey/customer text

## UX
- One search box
- Category tabs
- Result count
- Clear action
- Result preview
- Result navigation to the original record

## Workflow guarantee
Search is read-only. Selecting a result must not change:
- Chat status
- Ticket status
- Follow-up status
- Customer status
- Service status
- Warranty status
- Survey status

## Data policy
No new database table or migration is introduced by this UI foundation.
Search should reuse existing application data sources.

## Performance principle
The eventual backend implementation should use indexed, scoped queries rather than loading every record into memory.

## Security principle
Search results must respect the current user's permissions and must not expose records the user cannot already access.

## .md

# SAZGAN  — Roles & Permissions

## Scope
Add the Roles & Permissions information architecture.

## Principle
Permissions must be enforced server-side. The UI checkboxes are only the administration interface and are not a security boundary.

## Permission groups
- Customers
- Conversations
- Tickets
- Follow-ups
- Products & Warranty
- Surveys
- Reports
- Administration

## Permission actions
Examples:
- View
- Create
- Edit
- Delete
- Reply
- Archive
- Manage
- Complete
- Export

## Security rules
1. Existing administrator access must not be removed automatically.
2. A user must never gain access merely because a button is hidden/shown.
3. Server-side authorization must protect every protected route/action.
4. Global Search must return only records the current user is authorized to see.
5. Reports export requires explicit export permission.
6. Role changes should be audited.

## Workflow guarantee
Adding permissions does not change the operational workflow. It only controls who may perform existing actions.

## Data policy
This UI foundation adds no database migration. The final backend integration must reuse the existing user/role model if present.

## .md

# SAZGAN  — A1 Global Responsive & CSS Stabilization

Changes in this build:
- Hub cards use a single authoritative responsive grid: 4 columns desktop, 3 tablet, 2 phone.
- Narrow phones (including 360px and typical 5-inch Android widths) remain two-column for `.sys-tile-grid`.
- Removed an older duplicate `.sys-tile` CSS block.
- Removed the 220px auto-fill constraint from `settings-modern.css` that caused one-column Hub cards on narrow screens.
- Added a final responsive CSS layer loaded after theme/component CSS.
- Hardened Settings/Theme preview and controls against page-level horizontal overflow.
- Fixed the Chat Inbox server-sync scope bug by sharing the state store between IIFEs.
- No database schema, workflow, routes, or Chat reply/quote behavior was intentionally changed.

Validation performed:
- Static CSS/HTML/JS source checks.
- Verified all templates using `.sys-tile-grid` inherit the global responsive layer.
- Verified `settings_display.html` preview is width-constrained on mobile.
- Browser/device E2E validation is still required on the target 5-inch phone.
