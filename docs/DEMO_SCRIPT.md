# 3-minute demo script
**0:00 Intro (30s)**: "I'm <name>. This is an on-call agent that remembers every incident. Same LLM, same prompt; the only difference is Hindsight memory."
**0:30 Problem (30s)**: UI at INC-101. Click *Triage without memory*: generic "roll back and check logs". Point out the cited incidents list is empty.
**1:00 Learn (30s)**: Click *Retain to memory* (engineer closes INC-101 with root cause: pool exhausted). Do the same for INC-102, INC-103 quickly.
**1:30 Payoff (60s)**: Select INC-104 (payments-api). *Without memory* → generic. *With memory* → cites INC-101, hypothesis "connection pool exhausted", plus a needs-approval item from the team rule. Show the recalled-memories panel.
**2:30 Reflect (20s)**: Click *Reflect: recurring patterns*; show synthesised themes.
**2:50 Takeaway (10s)**: Run `make demo` and show the accuracy line. Say what surprised you (e.g. novel incidents don't improve; repeats do).
