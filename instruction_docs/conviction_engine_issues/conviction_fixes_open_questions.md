# Conviction Engine Fixes — Open Questions Before We Build

While mapping the 28 July note onto the actual code I found a bunch of spots where the note either says a rule is not specced yet or just does not give a number. Rather than picking something myself and quietly baking it into the code I am writing all of them down here. For each one I explain what the note said why it matters and give a couple of options with a recommended pick. Just write your answer under each one and I will build against that.

## 1 How much of the business type work do we build

The note lists nine business types in section 5.7 but only high margin hardware comes with a real specced fix. The other five new ones like banks insurers REITs biotech and deep value each need their own valuation approach and none of that exists in code today. My recommendation is to build only high margin hardware now and just add a coverage incomplete flag for the other five so they stop quietly getting scored as generic compounders. The other option is to build all nine properly including the bank and insurance and REIT and biotech logic which is a much bigger job on its own.

Your answer

## 2 What margin cutoff defines high margin hardware

The note is clear that the fifty percent net margin rule used for NVDA this session was just an on the spot guess and should not be built. But the new hardware bucket still needs some margin number to decide who qualifies. I would go with forty percent trailing net margin since it comfortably separates thin margin hardware makers from a name like NVDA sitting around sixty percent. The other option is fifty percent to match the number used in this session even though it was for a different rule.

Your answer

## 3 Should G2 exclusion follow the new bucket or the raw sector

The note says G2 should be dropped from sourcing for hardware and semiconductor names since it measures software satisfaction not chip competitiveness. The question is whether that exclusion should apply to any semiconductor or hardware company by sector, or only to the ones that actually cross the new margin threshold into high margin hardware. I would key it off the raw sector directly since G2 is equally irrelevant to a lower margin chip company too. The other option is to key it only off the new bucket which means thinner margin hardware names would still see G2 as a source.

Your answer

## 4 What happens to the verdict when coverage is incomplete

If we add the coverage incomplete flag from question one we still need to decide what it actually does. The note talks about wanting a visible flag rather than a silently generated score which reads like it should stop a normal buy or sell verdict from being produced at all. My recommendation is to hard gate it so the verdict becomes something like coverage incomplete with sizing at zero, the same way the engine already hard gates on yield trap or weak financial strength. The softer option is to just show a warning banner while still generating a normal score underneath.

Your answer

## 5 What counts as a buyback suspension

The note gives one real example, GOOGL going from twenty eight point three billion in buybacks to zero, and says this should already have triggered a full recalculation. There is no code for this today, only a separate share count based buyback score that measures something different. My recommendation is to fire this trigger when buyback spend drops by ninety percent or more compared to the prior period, as long as the prior period was meaningful, say above one hundred million. A simpler alternative is to only fire when buybacks go to close to zero regardless of how big the prior period was.

Your answer

## 6 What size dividend cut should trigger a recalc

The original spec lists dividend cut as one of six recalculation triggers but never says how big a cut needs to be. I would say any decrease in the declared annual dividend per share should count, since real dividend cuts are rare and almost always meaningful. The other option is to only count cuts of ten percent or more so small rounding level changes do not fire the trigger.

Your answer

## 7 Where does the revenue miss trigger get its expected number from

The revenue miss over ten percent trigger is already in the original spec but a miss needs something to be measured against. My recommendation is to use yfinance's own analyst revenue estimate field since that is already the data source used elsewhere in this engine and needs no new key. The alternative is to skip this trigger for now since there is no fully reliable consensus number wired in yet, and just note it as deferred instead of guessing.

Your answer

## 8 Does the supply constraint flag move the score at all

Section 9 of the note is where this flag comes from, based on the GOOGL transcript showing a supply constrained backlog story rather than a demand slippage story. The note calls this a positive demand signal paired with a margin risk but never gives an actual scoring rule. I would keep it as information only with no automatic score change, since inventing a number here would repeat the same kind of guess the note warns against elsewhere. The other option is to give it a small automatic positive nudge on a dimension like growth trajectory.

Your answer

## 9 What tax rate do we use for the adjusted EPS work

The note says one off items should be tax effected at the marginal rate when building adjusted EPS but does not name a rate. I would use a flat twenty one percent US federal statutory rate since it is simple and easy to explain. The alternative is a flat twenty five percent blended rate to roughly account for state taxes as well.

Your answer

## 10 Should adjusted PE always replace raw PE or only sometimes

The GOOGL example in the note is specific, its trailing PE of about sixteen times is misleading because of a one time gain of around ninety eight billion, and the note says not to feed that into the percentile tax calculation. It does not say whether every ticker should always use the adjusted number going forward or only when the distortion is large enough to matter. My recommendation is to only substitute the adjusted PE when the one off items are material, say more than five percent of trailing net income. The other option is to always use the adjusted number for every ticker once the pipeline exists.

Your answer

## 11 How much of the universe gets rerun once this is built

The note says business type reclassification should eventually apply across the full model universe of around one hundred ninety three tickers, not just NVDA and GOOGL. My recommendation is to run a full recalculation across the entire universe once everything above is built, the same way earlier fixes like the PE history rollout were handled, so nothing is left half migrated. A narrower option is to only rerun the tickers whose business type actually changes under the new rule and leave the rest on their normal schedule.

Your answer

That covers all eleven spots where the note either says a rule is not specced yet or where comparing it against the real code turned up a gap it did not anticipate. Everything else in the note is clear enough to build directly without needing a judgment call from you first.
