# AI-Powered Onboarding Blueprint

## Vision
First-time users answer 5 questions. AI generates a personalized financial blueprint (goals, targets, allocation, timeline). The app feels tailor-made from minute one.

## Trigger
- New user (0 goals, 0 portfolio data) lands on Blueprint page
- OR user clicks "Regenerate Blueprint" in settings

## Onboarding Flow

### Step 1: Income Range
- Options: ₹25k-50k / ₹50k-1L / ₹1L-3L / ₹3L-5L / ₹5L+ / Prefer not to say
- Purpose: calibrates target amounts

### Step 2: Investment Goals (multi-select)
- Retirement
- Buy a house
- Emergency fund (6 months expenses)
- Children's education
- Wealth building / Financial freedom
- Car / Vacation
- Custom (free text)

### Step 3: Risk Tolerance
- Conservative (capital preservation, FDs, gold)
- Moderate (balanced — stocks + debt)
- Aggressive (growth, equity-heavy)
- Purpose: shapes allocation recommendation

### Step 4: Timeline
- 1-3 years (short-term)
- 3-5 years (medium)
- 5-10 years (long-term)
- 10-20+ years (retirement)

### Step 5: Markets & Currency
- India only (INR)
- US only (USD)
- Both (mixed currency goals)

## AI Output (Structured JSON)
LLM receives answers + system prompt. Returns structured response:

```json
{
  "goals": [
    {
      "name": "Emergency Fund",
      "target_amount": 300000,
      "target_currency": "INR",
      "deadline": "2027-06-01",
      "icon": "emergency",
      "color": "amber",
      "reasoning": "6 months of expenses at ₹50k/month"
    },
    {
      "name": "Retirement Corpus",
      "target_amount": 50000000,
      "target_currency": "INR",
      "deadline": "2050-01-01",
      "icon": "retirement",
      "color": "blue",
      "reasoning": "₹5Cr target assuming 8% CAGR over 25 years"
    }
  ],
  "allocation": {
    "equity_pct": 60,
    "etf_pct": 20,
    "debt_pct": 10,
    "gold_pct": 10
  },
  "monthly_saving_suggestion": 25000,
  "insights": [
    "Start SIP of ₹15k in Nifty 50 index fund",
    "Keep 3-6 months expenses in liquid fund",
    "Gold ETF better than physical gold for liquidity"
  ]
}
```

## Database Changes
- Table: `onboarding_responses` (user_id, responses JSON, ai_output JSON, created_at)
- Flag on user: `onboarding_completed` boolean

## Backend Endpoints
- `POST /onboarding/generate` — accepts answers, calls LLM, returns plan
- `POST /onboarding/accept` — creates goals from AI plan, marks onboarding done
- `GET /onboarding/status` — check if user needs onboarding

## Frontend Components
- `OnboardingWizard` — full-screen overlay, step-by-step cards with animations
- `BlueprintPreview` — shows AI-generated plan before acceptance
- Auto-redirect to wizard when new user detected on Blueprint page

## LLM Integration
- Use existing `create_llm_service()` (Gemini/Groq)
- System prompt: "You are a certified financial planner for Indian retail investors..."
- Structured output via JSON mode
- Fallback: if LLM unavailable, use formula-based defaults (no AI, just math)

## UX Details
- Wizard: one question per screen, large buttons, progress dots
- After generation: show plan with "Looks good!" / "Edit" / "Regenerate"
- Accepted plan auto-creates goals with entries
- User can always re-run from Settings

## Edge Cases
- LLM rate limited: show formula-based defaults with note "AI unavailable, showing estimates"
- User skips onboarding: show standard empty Blueprint page with "New Goal" button
- User re-runs: overwrites previous AI plan (after confirmation)

## Implementation Order
1. DB migration (onboarding_responses table + user flag)
2. Backend endpoint (generate + accept)
3. System prompt design + JSON schema
4. Frontend wizard component
5. Integration + Blueprint page detection
6. Testing with different answer combinations
