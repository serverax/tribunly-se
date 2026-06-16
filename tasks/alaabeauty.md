CODEX MASTER ORDER  -  ALAA BEAUTY PLATFORM

Project: Alaa Beauty
Repo: https://github.com/serverax/beauty
Local path: D:\beauty

Goal:
Build Alaa Beauty as a production-grade ladies-only beauty booking platform with customer registration, booking, admin, reviews, gallery, payments, SEO, GDPR, and AI features for beauty advice and marketing.

Use the existing handoff and roadmap as the source of truth. Do not skip phases. Each phase must build, wire, test, and prove before moving to the next phase.

Core rules:
1. Never push directly to main.
2. Work phase by phase.
3. No fake PASS.
4. Screenshots alone are not proof.
5. A phase is PASS only when code exists, wiring exists, tests pass, and proof exists.
6. Do not change business names, phone numbers, or brand direction without permission.
7. Keep design luxury, feminine, calm, elegant, mobile-first, Arabic/English.
8. Do not deploy production unless explicitly ordered.

Required stack:
Frontend: Next.js, TypeScript, Tailwind
Backend: Node.js, NestJS or Express, TypeScript
Database: PostgreSQL, Supabase-compatible schema
Infrastructure: Docker Compose
Testing: Playwright, API tests, DB proof scripts

PHASE 0  -  Local Foundation
Build:
- Docker Compose
- PostgreSQL
- Backend service
- Frontend service
- Health endpoints
- Migrations
- Seed data
- Proof scripts

Proof required:
- docker compose up works
- frontend loads
- backend health works
- database connected
- migrations applied
- seed data exists
- tests pass

Do not start Phase 1 until Phase 0 PASS.

PHASE 1  -  Luxury UI/UX Foundation
Build:
- Home page
- Services page
- Bridal page
- Gallery page
- Reviews page
- Contact page
- Booking page
- Arabic/English structure
- Responsive mobile-first layout
- Accessibility improvements
- Luxury animations

Proof:
- Playwright responsive tests for 360, 390, 430, 768, 1024, 1440
- No console errors
- Lighthouse target 90+
- Mobile menu tested
- Arabic/English switching tested

PHASE 2  -  Service Catalogue
Build:
- services table
- service_categories table
- pricing/packages support
- service API
- dynamic service cards
- category filters
- bridal and home visit packages

Proof:
- API returns real DB services
- frontend consumes API
- filters work
- tests pass

PHASE 3  -  Customer Registration & Login
Build customer authentication before advanced booking.

Registration methods:
1. Email/password
2. Facebook Login
3. Future-ready Google Login

Required features:
- Register
- Login
- Logout
- Forgot password
- Reset password
- Email verification
- Customer profile
- Customer booking history
- Marketing consent
- Terms acceptance
- Login audit logs

Required tables:
- customers
- customer_auth_accounts
- customer_sessions
- oauth_accounts
- password_reset_tokens
- login_audit_logs

Required APIs:
- POST /api/auth/register
- POST /api/auth/login
- POST /api/auth/logout
- POST /api/auth/forgot-password
- POST /api/auth/reset-password
- GET /api/auth/me
- GET /api/auth/facebook
- GET /api/auth/facebook/callback

Frontend pages:
- /login
- /register
- /account
- /account/profile
- /account/bookings
- /forgot-password
- /reset-password

Rules:
- Build email login first.
- Do not build Facebook OAuth until email auth is tested.
- If Facebook does not return email, ask customer to enter email manually.
- Guest booking must still be allowed.
- After guest booking, prompt customer to create account.

Proof:
- Register works
- Login works
- Logout works
- Password reset works
- Facebook login works
- Account page works
- Booking links to customer account
- Admin can see customer source: email, Facebook, or guest

PHASE 4  -  Booking System
Build:
- booking requests
- studio booking
- home visit booking
- availability
- travel fee calculation
- booking status workflow
- customer booking linkage
- guest booking support

Tables:
- bookings
- availability_blocks
- travel_zones
- booking_status_history

Statuses:
- requested
- reviewed
- accepted
- rejected
- deposit_pending
- confirmed
- completed
- cancelled

Proof:
- logged-in customer booking works
- guest booking works
- home visit fee works
- admin can review booking
- booking appears in customer account
- tests pass end-to-end

PHASE 5  -  Admin Dashboard
Build:
- admin login
- booking management
- customer management
- service management
- reviews management
- gallery management
- calendar view
- AI dashboard placeholder

Admin can see:
- registered customers
- guest customers
- booking history
- review history
- consent status
- last login
- auth source

Proof:
- admin login works
- admin can manage bookings
- admin can view customers
- admin can update booking status
- audit logs created

PHASE 6  -  Reviews
Build:
- verified reviews
- review invitations
- review moderation
- public review display
- Google Review link support

Tables:
- reviews
- review_invites

Proof:
- completed booking can receive review invite
- public review appears only after approval
- unapproved review hidden
- tests pass

PHASE 7  -  Gallery
Build:
- gallery upload
- gallery categories
- before/after slider
- consent tracking
- photo approval

Tables:
- gallery_items
- photo_consents

AI support:
- AI captions
- AI hashtags
- AI category suggestions

Proof:
- upload works
- category filter works
- before/after works
- consent required
- tests pass

PHASE 8  -  Notifications
Build:
- Resend email integration
- booking confirmation email
- booking reminder email
- review invitation email
- admin notification email
- WhatsApp click-to-chat links

Tables:
- email_logs
- notification_logs

Proof:
- email logs created
- templates render correctly
- failed email handled safely
- WhatsApp links use correct number: 07825957159 / 447825957159

PHASE 9  -  Payments
Build:
- Stripe deposit payments
- bridal deposit
- payment verification
- webhook handler
- payment status linked to booking

Tables:
- payments
- stripe_events

Proof:
- checkout session created
- webhook verified
- booking status updates after payment
- failed payment handled
- tests pass

PHASE 10  -  SEO
Build:
- local SEO pages
- metadata
- sitemap
- robots.txt
- structured data
- service schema
- review schema
- local business schema

Location targets:
- Mansfield
- Nottingham
- Chesterfield
- Sheffield
- nearby areas

Proof:
- sitemap works
- robots works
- metadata exists
- structured data validates
- Lighthouse SEO tested

PHASE 11  -  Security & GDPR
Build:
- JWT/session protection
- password hashing
- rate limiting
- CSRF protection where required
- audit logging
- GDPR consent tracking
- privacy page
- terms page
- data deletion page
- cookie controls
- Cloudflare Turnstile-ready hooks

Proof:
- protected routes protected
- invalid login blocked
- rate limiting tested
- audit logs created
- deletion request workflow exists

PHASE 12  -  End-to-End QA
Test:
- full customer journey
- full guest journey
- full admin journey
- booking journey
- review journey
- payment journey
- mobile journey
- security basics
- performance
- accessibility

PASS requires:
- all tests pass
- screenshots saved
- logs saved
- proof report written

PHASE 13  -  AI Beauty Advisor
Build AI module after core platform works.

Features:
- beauty advice chat
- bridal advice
- haircare advice
- makeup advice
- face-shape suggestions
- event preparation advice
- aftercare advice
- logged-in customer profile awareness with consent

Tables:
- ai_conversations
- ai_messages
- ai_recommendations
- customer_beauty_profiles
- ai_consent_logs

Rules:
- AI must not give medical advice.
- AI must not use customer profile unless consent exists.
- AI must escalate uncertain booking questions to Alaa/admin.
- AI answers must be warm, clear, and business-safe.

APIs:
- POST /api/ai/advice
- POST /api/ai/chat
- GET /api/ai/history
- POST /api/ai/consent

Proof:
- AI chat works
- profile-aware advice works only with consent
- no-consent mode works
- unsafe answers blocked
- chat history saved

PHASE 14  -  AIA Marketing Agent
Build AI marketing assistant for Alaa Beauty.

Features:
- Facebook post generation
- Instagram caption generation
- TikTok/Reels ideas
- campaign ideas
- bridal campaign generator
- seasonal promotion generator
- offer wording
- WhatsApp broadcast drafts
- email marketing drafts
- hashtag suggestions
- local SEO content ideas

Tables:
- marketing_campaigns
- marketing_messages
- ai_marketing_outputs
- social_post_drafts

APIs:
- POST /api/ai/marketing/generate
- POST /api/ai/marketing/campaign
- GET /api/ai/marketing/history
- POST /api/ai/marketing/approve

Rules:
- AI creates drafts only.
- No automatic public posting until admin approval exists.
- Marketing must match Alaa Beauty tone: luxury, feminine, warm, trustworthy.
- Avoid fake claims.
- Avoid medical/skin treatment claims unless manually approved.

Proof:
- AI generates Facebook post
- AI generates Instagram caption
- AI generates bridal campaign
- admin can approve/save draft
- history saved
- tests pass

PHASE 15  -  AI Receptionist / WhatsApp Assistant
Build:
- customer FAQ answers
- price guidance
- booking guidance
- opening hours
- home visit guidance
- bridal enquiry flow
- WhatsApp handoff to Alaa

Rules:
- AI must not confirm booking without booking workflow.
- AI must not invent availability.
- If unsure, escalate.

Proof:
- FAQ answers work
- booking handoff works
- escalation works
- no fake availability

PHASE 16  -  AI Sales & Retention
Build:
- package recommendations
- rebooking suggestions
- abandoned booking follow-up drafts
- customer retention messages
- birthday/occasion message drafts
- bridal upsell suggestions

Proof:
- suggestions based on real customer data
- consent respected
- admin approval required before messaging

PHASE 17  -  AI Analytics Dashboard
Build:
- booking insights
- revenue insights
- best services
- repeat customers
- campaign performance
- review trends
- AI recommendations for business growth

Proof:
- dashboard uses real data
- no fake metrics
- reports generated

Final required documentation:
- HANDOFF.md updated
- PROJECT_MASTER.md updated
- TESTING_STATUS.md updated
- API_REGISTRY.md updated
- DATABASE_SCHEMA.md updated
- AI_FEATURES.md created or updated
- SECURITY_GDPR.md created or updated
- PHASE_PROOF_REPORT.md created for every phase

Final instruction:
Start from the current repo state.
Inspect branch, git status, package files, Docker files, tests, and existing reports.
Then continue only from the next incomplete phase.
Do not rebuild from scratch unless the repo is broken.
Do not claim PASS without proof.