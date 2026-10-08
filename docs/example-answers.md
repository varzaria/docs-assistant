# Example answers

Real questions and answers from the test runs, copied unedited from `evaluate.py`'s output. Numbers in square brackets are citations; the pages they point to are listed under each answer. Each example shows one behaviour the assistant was tested for.

## Café documents (10 pages)

### 1. Gives the current rule, not the outdated one

**Q: What discount do staff get?** (design A, graded correct, 4.8 s, $0.012)

> Staff get **25% off food and drink when not on shift**, increased from 20% [1] as of 1 February 2026 under the January 2026 policy update.
>
> - **Guest discount ended:** The discount for an accompanying guest is discontinued. [1] The 2025 handbook had said the discount also applies to one guest accompanying the staff member. [2]
> - **Still excluded:** Retail coffee beans and gift cards are still excluded. [1]
> - **On shift:** Staff may have one free hot drink and unlimited filtered water during each shift. [2]

*Sources: [1] policy update, January 2026, p.1 · [2] staff handbook, p.2*

**What it shows:** the 2025 handbook says 20%; a January 2026 memo changed it to 25% and dropped the guest discount. The assistant gives the current rule and says what it replaced.

### 2. Says when it doesn't know

**Q: What is the Wi-Fi password?** (design A, graded correct, 4.8 s, $0.007)

> I couldn't find the Wi-Fi password in the company documents. Please ask the café manager, Ciarán.

**What it shows:** no invented answer. It points the person to someone who can help, using the manager's name from the documents.

### 3. Applies a rule to a real situation

**Q: A Leinster Dairy delivery arrives at 9°C. Should I accept it?** (design A, graded correct, 7.7 s, $0.013)

> No, reject it. Reject any chilled delivery above 8°C. [1] Deliveries between 5°C and 8°C can be accepted only if they go into the fridge immediately [1], but 9°C is over that limit.
>
> What to do next:
> - Sign the delivery note, write any shortages or rejected items on it, and photograph it. [1]
> - Report damaged, missing or rejected items to the supplier on the same day and ask for a credit note. [1]
> - Give the credit note to the café manager, who checks it against the next invoice. [1]

*Sources: [1] purchasing policy, p.2*

**What it shows:** the documents never mention 9°C; the assistant compares it with the thresholds and adds the next steps from the same policy.

### 4. Where keyword search goes wrong

**Q: What breaks do I get on a 7-hour shift?**

Design A (read everything), graded correct, 6.5 s, $0.010:

> On a 7-hour shift you get a 15-minute paid break plus a 30-minute unpaid lunch break [1], since it's more than 6 hours. [...]

Design B (search first), graded incorrect, 4.2 s, $0.017:

> I couldn't find the break entitlement for a 7-hour shift in the company documents; the section that would cover it isn't included in what I have. [...] For how many breaks you get and how long they are, please check with Ciarán, the café manager.

*Sources: staff handbook, p.1 (design A); staff handbook, p.2 (design B)*

**What it shows:** the handbook talks about shifts of "more than 6 hours", never "7-hour", so keyword search didn't retrieve the right passage. Design B failed safely, saying it couldn't find the answer instead of guessing.

## Irish sustainability reports (467 pages)

### 5. Compares two companies' reports

**Q: When do Kerry Group and Ryanair each aim to reach net zero?** (design A, graded correct, 5.3 s, $0.108)

> Both companies target 2050, with a slight difference in wording:
>
> - **Kerry Group** aims to reach net zero *before* 2050. It states it is committed to achieving Net Zero before 2050 [1], and in 2025 it received Science Based Targets initiative (SBTi) approval for our net zero target and interim targets to 2030 [2].
> - **Ryanair** aims to reach net zero *by* 2050. [...] It also notes it may have to continue offsetting beyond 2050, however this would be a last resort [4].

*Sources: [1] Kerry Annual Report 2025, p.20 · [2] p.84 · [3] Ryanair Sustainability Statement FY26, p.16 · [4] p.26*

**What it shows:** it pulls the answer from two different reports and notices a real difference in wording ("before" versus "by").

### 6. Doesn't fall for a near miss

**Q: What is Glanbia's Scope 3 emissions target?** (design A, graded correct, 5.4 s, $0.104)

> I couldn't find Glanbia's Scope 3 emissions target in the reports provided. The documents are sustainability and annual reports for Bank of Ireland, Kerry Group and Ryanair, not Glanbia.
>
> Glanbia is mentioned only once, as one of the companies in the peer group [1] Kerry uses to measure total shareholder return for executive pay [...]. That reference contains no information about Glanbia's emissions or targets.

*Sources: [1] Kerry Annual Report 2025, p.105*

**What it shows:** Glanbia does appear in the reports, but only in a pay-benchmark list. The assistant finds that mention, explains why it doesn't answer the question, and doesn't fill the gap with general knowledge.

### 7. Why search struggles with long reports

**Q: Has Bank of Ireland reached 100% renewable electricity?**

Design A (read everything), graded correct, 3.5 s, $0.103:

> Yes. Bank of Ireland reports that as at 31 December 2024, all electricity energy supply is renewable. [1] This meets its target to increase annual sourcing of renewable electricity to 100% by 2025 [1], a year early.
>
> One caveat: the own-operations figures do not include Davy that was acquired by the Group in 2022. [1]

Design B (search, 5 passages), graded incorrect, 5.6 s, $0.021:

> **I couldn't find evidence in the provided report that Bank of Ireland has reached 100% renewable electricity.** The 2024 Sustainability Report states the target [...] increase annual sourcing of renewable electricity to 100% by 2025. [1]

*Sources: Bank of Ireland Sustainability Report 2024, p.13 (both designs)*

**What it shows:** the answer sits in a footnote on the same page as the target. Reading everything found the footnote and its caveat; search retrieved the target but not the footnote, so it couldn't confirm the result. This is the kind of miss that retrieving 20 passages instead of 5 mostly fixed.
