# From Service to Agent-Oriented Architectures

*Components, Services, Tools and AI*


## Learning Objectives

This reading focuses on *design reasoning* rather than framework mastery.

Throughout this piece, we adopt a design perspective on AI systems.

Rather than focusing on specific frameworks or APIs, the goal is to reason about:

- which **system-level properties** we want from AI-enabled systems,
- which **perspectives** must be considered when designing them,
- which **abstractions** help manage complexity and scale,
- and which aspects must be **explicitly specified or standardized** for systems to be interoperable, safe, and evolvable.

The historical examples and modern tool integrations discussed below are used as concrete anchors for this broader design discussion.

By the end, students should be able to:

- Trace the evolution of **abstractions for distributed systems** (components → services → tools) and explain why new abstractions emerge when existing ones fail.

- Analyze AI integration from **provider and consumer perspectives**, including how these differ when the consumer is a human versus an AI agent.

- Explain why some integration standards **succeed or fail**, using SOAP/WSDL/UDDI vs REST as a case study.

- Distinguish what **must be standardized** versus what can remain flexible when building AI-enabled systems.

- Identify **open problems** in AI+tools integration (autonomy, testing, observability) that lack mature abstractions.


## Assessment (Course Use)

This reading may be assessed, but assessment is optional when the material is used as a standalone reading.

Assessment focuses on whether students can translate design reasoning into engineering reality.

Students will be evaluated on whether they can design and implement services that are:

- **Testable**
  - clear and explicit contracts,
  - well-defined inputs, outputs, and error modes,
  - behavior that can be validated independently of the AI model.

- **Observable**
  - meaningful logging and tracing of tool usage,
  - visibility into decisions, failures, and side effects,
  - ability to inspect and replay executions.

- **Autonomous, with explicitly justified boundaries**
  - clear explanation of what the system may do autonomously,
  - where human approval is required,
  - and why these boundaries are appropriate.

- **Guarded**
  - safety and policy constraints enforced by design,
  - protection against misuse, prompt injection, or unintended side effects,
  - explicit handling of failure and uncertainty.

The emphasis is not on using a specific framework, but on demonstrating sound system design choices and the ability to reason about their implications.


### A note on terminology

In this essay, we use the following terms with specific intent:

- **Component**
  A unit of functionality used *within* a system boundary, typically invoked in-process
  (e.g., libraries, modules, classes).

- **Service**
  A remotely accessible capability exposed across a network boundary, with an explicit
  interface and independent lifecycle.

- **API**
  A contract describing how a service or component can be invoked, including inputs,
  outputs, and interaction patterns.

- **Tool**
  A callable capability exposed to an AI system or agent runtime, typically wrapping a
  service or API, and designed to be invoked programmatically by a model rather than a
  human.

- **Agent**
  An AI-driven system that can reason over goals, decide when to invoke tools, and
  orchestrate actions over time, potentially with limited autonomy.

These distinctions are not absolute, but they are useful for reasoning about system
design, responsibilities, and where explicit contracts and safeguards are required.

---

## 1. From monolithic software to modules and classes
In the beginning, software was a monolith.
We had code written on punching cards.

Then, with storage and data transfer we could write programs that consist of many lines of code and run them repeatedly.

Computers got bigger, programs got bigger too also because we could now handle more complex functionality.
With that we had to organize the code - even if it was written by one programmer. Why?
Because we need to manage complexity, and as Julius Ceasar teaches us, we do so by divide and conquer.

As complexty grows, we need teams to write software. Therefore we naturally need to divide the work and we do so using modules and packages and objects and classes and other abstractions.

What these abstractions have in common ia a desire to encapsulate logic, minimize coupling across components so that it was possible to evolve each component while keeping the overall code working.

With multi-person teams classes and modules also allow to divide responsibility while keping a clear and clean "contract" across teams.

Internally, communication about features and interfaces was provided via documentation, oriented to developers.

**Versions** were managed somewhat ad hoc from a conceptual perspective and, in practice, by working on a shared repo via some variations of git.
The layer of "standardization" was mostly defined by the programming language: all components were in C++, or in Java, and the compiler knew how to put pieces together.




## 2. Services
With the internet it becomes possible to offer functionality over the net (internally, as an intranet - but also externally).
People started building more and more complex "stuff" - and by stuff here I mean also databases and all sorts of resources - and providing access to them on the fly, without the need of packaging and releasing software.

Initially the ability to access resources created massive confusion. Teams built point-to-point integrations, shared databases directly, and created tight coupling that made systems brittle and change expensive.


![Integration wild west - many protocols, no standards](figs/integration_wild_west.png)
*Fig: Before standardization: every integration required custom protocols and middleware.*

In other words, everybody was offering and using "services", also - and mainly - internally, often without knowing they were doing so. Something was accessible and therefore it became accessed.
When you have code by team A accessing code or data from team B, you do need coordination, just like you need it when you are consuming a class built by another team.
This is even more so id you are exposing data as well as structural or implementation detail that you as a dev team need to be able to modify without breaking other services.



### The Bezos API Mandate (circa 2002)

This chaos led to dictats such as the famous Jeff Bezos memo at Amazon:

> 1. All teams will henceforth expose their data and functionality through service interfaces.
> 2. Teams must communicate with each other through these interfaces.
> 3. There will be no other form of interprocess communication allowed: no direct linking, no direct reads of another team's data store, no shared-memory model, no back-doors whatsoever. The only communication allowed is via service interface calls over the network.
> 4. It doesn't matter what technology they use. HTTP, Corba, Pubsub, custom protocols — doesn't matter.
> 5. All service interfaces, without exception, must be designed from the ground up to be externalizable. That is to say, the team must plan and design to be able to expose the interface to developers in the outside world. No exceptions.
> 6. Anyone who doesn't do this will be fired.

This memo crystallized the notion of **service** and the importance of providing access to data and functionality via a relatively stable interface that provides a "contract" between service providers and consumers.

The key insight was not technical — it was organizational: **treat every consumer as if they were external**, even internal teams. This forces clean boundaries and explicit contracts.

At this time we also have the birth and rise of SaaS applications and vendors — which appeared like magic to many customers. Simple things, such as the ability to rename a column on an ITSM application, felt incredible to customers used to packaged software upgrade cycles.

### Service-oriented Architectures

While components were managed by the same org, now services are priovided both internally and externally.
This proliferation of service gave rise to the notion of Service-Oriented Architectures. The core idea here was to deliver functions via some sort of "stable" interface (people used horrible terms such as "well-defined").
The opportunity was for service providers to offer access to their services over the web and for consumer to use such services.

Some of the concepts around SOA are described in the book below - now old, but with many concepts still applicable because it was built to survive trends (but not AI and LLMs...)

![A true masterpiece on Web services](figs/best_sellers.png)
*Fig: No words can describe such an awesome work of art and science.*

Back then, it was still legal to use Comics Sans as a font, and so many pictures used it. 


![Web services enabling B2B integration across organizational boundaries](figs/5.5.1_web_services.png)
*Fig: Web services standardize protocols, eliminating the need for many different middleware infrastructures. Internal functionality becomes available as a service.*


![B2B integration with message brokers and adapters](figs/5.5.2_manual.png)
*Fig: While B2B integration via message brokers is conceptually possible, it rarely happens in practice due to lack of trust, autonomy, and confidentiality.*


The *kind* of questions we needed to ask - and answer - back then are similar to the ones we need to ask now:

- what do we need for services to be able to interact?
- how can we do so reliably and in a manner that is robust to change, errors, and to the vagaries of the average, distracted developer?
- what opportunites should we capture? how to maximize the potential?
- **which kind of specifications, agreement ("standard"), abstractions, middleware and "best" practices do we need?**


Correspondingly, this opportunity gave rise to the question: how do we facilitate exposing services? how do we facilitate consuming services?

#### Description, Discovery, Interaction
At first, developers started tackling service description, discovery and interaction.
As we move across the net, and away from the notion of one compiler bundling code together, the question becomes
1. how do we describe services so that other people can use them,
2. how does the communication take place
3. how do we even become aware of the existance of services

![Service description and discovery stack](figs/5.5.8.png)
*Fig (ca year 2004): The layers needed for service interoperability: common base language, interfaces, business protocols, properties and semantics — plus directories for discovery.*

The problems applies both to machines and humans. First, it was "solved" for humans.
**And this is interesting, as humans are more or less intelligent agents! So there may be lessons we can take.**

Humans can access services via html sent over http. They become aware of the service via ads or web search. And they consume it based on their own intelligence, or lack thereof.
The HTML page desrcibes to a human how to use the service.
A new version simply meant a new web pages, which is served via reload of the page.
Because the consumer is a human, changes are ok as long as they are not too confusing for humans. A/B testing was also used to understand which human interface was more condusive of higher usage, hence the orange-colored buttons we now see.




![The World Wide Web as some early version of tool calling](figs/www.png)
*The World Wide Web as some early version of tool calling*

Back then the direction towards automation did not include AI. Most interactions were human to service and service to database, with the occasional information aggregator.
Infornation aggregation happened via either humans (you are the aggregator) or APIs/SOA.

For SOAs, the question is - what if we want to offer a service to be consumed by a program, or, what if we want to consume such a service.
With programmatic access we have both opportunities and problems. A problem is that our client sofwtware may not be able to understand the HTML and how to use the service. An opportunity is that in theory we could, as a client, scan for services automatically (eg airline reservation services), identify at run time the one that best fits our need, and call it. At scale.
To solve the problems and capture the opportunities companies came up with "standards", or, specifications that they hoped would become standards.
Prime examples of such specifications were SOAP, WSDL, and UDDI and it is very informative to think and study what they were trying to specify, why, and why they failed.


### SOAP, WSDL, and UDDI: The First Odd Attempt at Machine-to-Machine Services

![The SOAP/WSDL/UDDI triangle](figs/uddi.webp)
*Fig: The classic web services triangle — Service Registry (UDDI) for discovery, WSDL for description, SOAP for communication.*

**[SOAP](https://www.w3.org/TR/soap12/)** (Simple Object Access Protocol) addressed the communication problem: how do two programs talk over the network in a language-agnostic way? SOAP defined a message format using XML. The idea was that regardless of whether your service was written in Java or C# or Perl, you could send and receive SOAP messages and understand each other. ([see example](https://www.w3schools.com/xml/xml_soap.asp))

**[WSDL](https://www.w3.org/TR/wsdl20/)** (Web Services Description Language) addressed the description problem: how does a client program know what operations a service offers, what parameters they take, and what they return? WSDL was an XML document that described the service interface - essentially, machine-readable API documentation. In theory, a client could read the WSDL and automatically generate the code needed to call the service. ([see example](https://www.w3.org/2001/03/14-annotated-WSDL-examples.html))

**[UDDI](https://www.oasis-open.org/committees/uddi-spec/doc/spec/v3/uddi-v3.0.2-20041019.htm)** (Universal Description, Discovery, and Integration) addressed the discovery problem: how do you find services in the first place? UDDI was meant to be a global registry - a kind of yellow pages for web services. Companies would publish their services to UDDI, and clients would query UDDI to find services that matched their needs. ([see example](https://www.tutorialspoint.com/uddi/uddi_usage_example.htm))

![External architecture of Web services](figs/5.13.external_arch.png)
*Fig (2004): The external architecture of web services — providers publish descriptions to a registry, requesters find and then interact with providers.*

The vision was compelling: a world where software could automatically discover services, understand how to call them, and integrate on the fly. Dynamic, loosely coupled, language-agnostic integration.



These specifications did not fail technically - they failed practically.

The main aspect to keep in mind is that average developers are average. One is almost tempted to say that average programmers are below average, and we wrestle with math and statistics on this one. But the fact is that if a "standard" (horrible name - there is no such thing - there are specifications and adoption of specifications) is intedned for humans, it has to be simple. Nobody can hope that millions of humans read complex specs and understand them - correctly, and in the same way.
Even if we "just" hope that developers will imnplement clients to simplify work for humans, simplicity matters and facilitates adoption.


**Complexity killed adoption.** SOAP messages were verbose. WSDL files were notoriously difficult to read and write. The tooling was fragile. What was supposed to simplify integration often made it harder. Developers found themselves debugging XML namespaces instead of building features.

**The discovery dream never materialized.** UDDI assumed that services would be published to public registries and discovered dynamically. In practice, companies did not want to advertise their internal services publicly, and the trust model for dynamic discovery was never solved. You do not just call an airline reservation service you discovered in a registry - you negotiate a contract, agree on SLAs, exchange credentials. The business reality did not match the technical abstraction.


Part of the problem was also XML: reading XML is a nightmare and maybe if JSON were a thing back then, they would have been more successful.

What happens in the end is that developers did not really adopt these specs. instead, they "used REST"
**REST won by being simpler.** While the enterprise world debated WS-* specifications (WS-Security, WS-ReliableMessaging, WS-AtomicTransaction...), developers started building APIs with plain HTTP and JSON. REST had no formal specification - just conventions. You could understand it by looking at examples. It was good enough, and good enough won.


In fact, REST is a non standard. or, a non spec. using REST means using nothing, pretty much. It's HTTP.
Somehow people felt cool becuause they then found some consistency on when to use GET vs POST vs DELETE and maybe PUT, but nobody cared too much about that, too.


The lesson here is important for AI integration: **standards succeed when they reduce friction, not when they maximize expressiveness.** A protocol that is easy to adopt beats a protocol that is theoretically complete. Or at least that was the case in the past.


So what we have instead of WSDL is web pages that describe APIs. Yes, there are attempts to "standardize" but they never went that far or be that useful. in the end you have developers (that is, humans) reading specs on web pages and implementing clients that call the service.

**Versioning** was handled a bit in ad hoc way, sometimes by adding version numbers to APIs. SaaS vendors grew increasingly allergic to maintaining many versions and developed a tendency to push clients on the latest versions rather than maintaining loads of versions active.



## 3. How Gen AI changes things: From Human to AI agents, from web services to "tools"

The above remained true also during the first wave of AI, where services exposed ML models such as classification or regression. Things start to change when we bring to the mix AI that is capable of understanding text — and more.

Consider that we have now three kinds of entities that want to use services on "the Web":

1. **Humans, we had those for a while
2. **Web services, since early 2000s and to this date
3. **AI agents capable of understanding and reasoning (no debating on "can AI agents think" - please)


The questions we ask are the same as for SOA:

- which opportunities arise and how we can leverage them?
- which abstractions and middleware do we need?
- what do we need to agree on as a minumum to enable interoperation?
- how do we create systems that are robust, reliable, and somewhat foolproof? 

And - as a developer and as a user - how do we make use of this.


And perhaps the most important question: we are designing specs to simplify the work for LLMs. but modern LLMs are way more powerful than humans. So - do we need anything more than what we have? and if so, why?


**What's different with AI agents?**

AI agents kind of combine the benefits of humans and services. ([diagram](https://miro.com/app/board/uXjVGNUbYRA=/?share_link_id=519477813799))

Like humans, they can read APi descriptions and learn how to interact with them.
This means that, in theory, they can figure out the intent of an API, gracefully handle variations in versions as the API evolve, reason when and if to use a tool, not just how.
Like services, they can do so at scale.

The AI agent is not us, however. so the above only works if the AI is 
- powerful enough to understand the services
- understands my goal and constraints
- has a very clear notion of what it does not know, and how much autonomy it has.

A good way to think about an AI agent is as a teammate that works with us.



With respect to Web Services, this is a significant shift. The SOAP/WSDL/UDDI dream of automatic integration might actually be achievable — not because we finally wrote the perfect spec, but because the client got smarter.
With respect to humans, however, there is somewhat less of a shift. in a way the new AI agents world, in a first approximation, is not different from the web and in fact if an agent can operate our computer and browser, it can function in the same way as we do.

But this also introduces new challenges:

- **Ambiguity**: when interfaces are "forgiving," there's room for misinterpretation.
- **Autonomy**: who decides what the AI can do? In our world, we do, in many cases. 
- **Non-determinism**: the same input might produce different outputs. This is not new to humans. We are very non deterministic.... 
- **New attack surfaces**: prompt injection, data exfiltration via tools, etc. This is not new per se: we did have attacks in the past as well, in the form of, for example, phishing. 

### The Service Provider perspective
In the above discussion we need to keep in mind our goals: we can be a provider of a service or a consumer.
If we provide a service we want our "web page" to be easy to understand, and secure.
We want that even if clients are AI agents. There may be less emphasis on "lets make the button orange so they click more", and maybe the wording can be reduced and same for boilerplate or CSS.
Just like we used to test if humans could interact with a page, we may have the same need here.

If we are instead AI agents, what we want is the ability to reliably understand what services do and how to invoke them. In addition, since agents operate somewhat on behalf of a person or as a teammate of a person, we also need to understand the **intention of the person, and how much **autonomy we are given.


Lets consider the provider perspective: what's our goal?
We want to maximize the "proper" use of our services and make sure our services are used efficiently, not just effectively.
Which problems do we need to solve? Which opporunities can we capture?

- Transport: Fist, we need transport. We need a basic form for clients to communicate. And we have that: HTTP, and, streamable http
- Then we need a way to describe our services. and we have that. in fact, we have many. we can use MCP specs, or we can use HTML. Notice that here the advantage is not so much provided by MCP and its specs since, if the client is intelligent, it can cope with html too. the benefit comes more from implementations such as FastMCP that make it easy for lazy axx programmers to document functions and parameters. This is indeed important: we need to be very clear on what parameter mean and be fool proof in their usage (eg make abundant use of assertions and constraints).
- Discovery is not really handled, or it is, but within a "server", so we can see the services it exposes. This is not much different from the above concept of description, only at a broader level. 
- As in the Web, we need to be intentional in what we expose, and where we require authentication. This is not a matter of standard but of good architectural design. There is a small difference in that, especially in auth, we are not mediated by the browser.
- Interactions can be bidirectional, but this was true before too (we had SSE and in general many ways for servers to update clients/browsers).

Notice that here **we kind of miss some notion of glue among the services**, that is, we need to be able not just to describe the invidual services but the set of services as a whole and give a sense for when to use what. This is very different from describing the services one by one. This part is missing in current "standards". 



![Agents](figs/agents_www.png)
*Agents are kind of analogous to the World Wide Web and tool calling*


The above is not very different than what we have with humans. There are however a few important differences:

- "Testing" is very different: with humans we do UX tests, maybe A/B testing but humans are more nuanced, maybe more gullible than AI clients? either way, we need to find a way to "test" that the average AI client written by the average, distracted, lazy developer can work well with our services. As a provider you need to conceive a way to test your services as AI agent.
- "Autonomy" is a different and new concept. In the Web it was clear that the human was always in the loop. In SOA there was no human but no autononmy as well - all workflows were scripted. Here, as a service provider, first we ask ourself if "is this our problem"? We could just offer the services and let the client's agent figure out how autononous it should be. In practice we can do that but, as service provider, we are likely to have collected wisdom over time on when human supervision is appropriate. In this case we can add to descriptions of services to encourage clients to ask for human supervision
- Server-side telemetry: as service providers we do not see the client's reasoning process for why they invoke what. However, we can log sessions and identify paths (sequences of operations) that tend to be common, and we may want to provide operations that implement such workflow. This is the same as to what we see with humans: if we see humans having to click 10 times the same sequence, we can offer the analogous of buttons such as "buy with one click".
- Last but not least, we - as provider - may decide to provide an additional "API" or service which is on top of what we offer and that provides a natural language interaction.
This has the benefit of 1. facilitating usage, if we believe that a NL interface may be for example more effective for flight search than an API, and 2. can help restrict usage and put in place all the checks so that autonomy is respected and ambiguity is resolved by asking humans to clarify.

Providing a NL interface is also an useful way to "test" our descriptions and resolve ambiguity.



An important point that providers tend to forget is that AI agents have the ability to read and understand A LOT of info on our services - so we should make sure to describe it to them, pointing them to a "page" where we provide a coherent picture of what we offer.
We don't just describe the services separately but how they are supposed to work and fit together. 
Since AI agents are smart, can digest even complex info and examples.



### The Consumer perspective

Here we think what abstractions and middleware we need to make it easy for AI agents to use services. Our role now is as implementor of a client agent.
We have already addressed transport, description and authentication - not much difference there. 
The key is that now we can have an entity that gets a declarative goal from humans (or other agents, for that matter - here we consider humans to be in essence limited versions of agents).

So our agent can read specs and understand how to interact. The challenge as agent developer is:
1. how to identify and limit the set of tools: our agent is capable but may not know which tool is "the best" if we give similar ones, or may get confused if it sees too many tools. This is the same as humans. As humans, we search on google and more or less trust what is on top of the non-sponsor list (basically, page rank and collaborative filtering do their thing). With agent we could do the exact same thing or we can be focused in what tools - and from what providers - we allow an agent to see. 
2. Autonomy, verification and Leash- this is the big item. How much autonomy should our agent have? How do we control that? how do we go in loops of work and check/verification/feedback?
I do not have any good answer here so far except that we should be explicit for what our agent can do and what it cannot do (probably more as allow-list rather than block-list). This means we also need to bake into the agent the ability to precisely represent a situation to human and asks the right questions to get useful feedback.
3. Telemetry here can help see when our agents go down the wrong path. Telemetry needs to expose workflows and help us identify (and indeed allow us to tag - declaratively or by example  - which workflows are "good" va "bad".
4. once we have telemetry we can also perform test runs for our agent, especially if the provider offers us a test playground.
5. Superhuman interactions. A key benefit is relaized when our agents start to interact with services in ways that is data dependent and that we did not anticipate. For example, it can decide to book hotels on Amex rather than booking because it autononously decide it is more conveninent or considers that the points we earn via Amex are valuable - based on our lifestyle.


### Between providers and consumers: Custom UI

One aspect that is somewhat in between providers and consumers and links all this with the web is the ability to build custom UX. once we have services exposed, we can have an agent that builds an UX that make sense for us as consumers and that possibly integrates in the same page content from multiple services based on what we need the most.


### The Tool-Calling Loop and Its Middleware

Tool integration in AI systems is not a single request–response interaction,
but an iterative loop in which a model reasons, invokes tools, observes outcomes,
and adapts its behavior over time.

This loop introduces new design concerns that were largely absent in traditional
API-based systems: control flow is no longer fully specified by the developer,
errors accumulate across steps, and decisions must be made under uncertainty.

As a result, the system requires middleware that mediates between the model and
the tools, enforcing budgets, retries, policies, and stopping conditions.
These concerns are not properties of individual tools, but of the orchestration
layer that binds them together.

Designing this loop explicitly—and deciding which parts are delegated to the
model and which are enforced by the system—is a central challenge in building
reliable AI-enabled systems.


### Novel Security, Safety, and Privacy Concerns

Tool-enabled AI systems introduce security and safety risks that differ
qualitatively from those of traditional software systems.

In these systems, untrusted inputs and untrusted outputs can both influence
control flow. A model may be manipulated into invoking tools in unintended ways,
or tool outputs may inject instructions back into the reasoning process.
This blurs traditional trust boundaries and creates new forms of confused
deputy problems.

Privacy concerns are similarly amplified: data may flow through models that are
not designed to enforce access control, and sensitive information may persist in
context or memory beyond its intended scope.

These risks cannot be addressed solely through API security or input validation.
They require explicit design of guards, policies, and isolation boundaries at the
level of the AI system itself.


### Context and Memory Management

AI systems operate not only on current inputs, but on constructed context that
combines instructions, interaction history, retrieved information, and memory.

Unlike traditional state management, this context is ephemeral, selectively
assembled, and interpreted probabilistically by a model. Decisions about what
to include, what to persist, and what to forget directly affect system behavior.

Long-term memory introduces additional challenges: information retained across
interactions can influence future decisions, raise privacy concerns, and create
feedback loops that are difficult to reason about or audit.

Treating context and memory as first-class design elements—rather than incidental
implementation details—is essential for building AI systems that are predictable,
safe, and aligned with user expectations.


## So....Which abstractions do we need, and what do we need to standardize? Is MCP the answer?

We identify six key dimensions of AI tool integration. For each, we assess what exists today, what gaps remain, and whether we need formal specifications, best practices, or further research.

---

### Dimension 1: Basic Service Description and Interaction

**The problem**: How do agents discover what a service does and how to call it?

**What we have now**:
- **For humans**: HTML pages, documentation sites, examples
- **For programs**: JSON Schema, OpenAPI, MCP tool definitions
- **Transport**: HTTP, SSE, WebSockets

**Key insight**: If the client is an intelligent agent, it can work with HTML just like humans do. An agent with browser access can read documentation, fill forms, and interact with services designed for humans. **MCP facilitates this by providing machine-optimized descriptions, but agents could function without it** — just as humans could always use websites before APIs existed.

**What MCP provides**:
- Structured tool definitions (name, description, input schema)
- Resource exposure (files, data the server wants to share)
- Prompt templates
- Transport options (stdio, SSE, streamable HTTP)

**Analogy**: MCP is to AI agents what APIs were to programmatic access. Humans could always scrape websites; APIs made it cleaner. Agents can always read HTML; MCP makes it cleaner. It is facilitation, not enablement.

**What we need**:

| Type | Content |
|------|---------|
| Best Practice | What to expose as tools vs. what to keep internal |
| Best Practice | Granularity: one coarse tool vs. many fine-grained tools |
| Best Practice | Naming and description conventions that reduce ambiguity |
| Best Practice | When to require structured input vs. accept natural language |
| Best Practice | Versioning strategies: how to evolve without breaking agents |
| Best Practice | Error messages that help agents recover or ask for help |

**Design questions on exposure and granularity**:
- Should `book_flight` be one tool, or `search_flights` + `select_flight` + `confirm_booking`?
- If tools are too coarse, agents cannot intervene mid-workflow
- If tools are too fine, agents must learn complex sequences
- The right granularity depends on where you want human checkpoints

---

### Dimension 2: Aggregate Service Description

**The problem**: We can describe individual tools, but not how they fit together.

**What we have now**:
- Per-tool schemas (MCP, OpenAPI)
- Human-readable documentation
- Ad-hoc system prompts listing tools

**What's missing**:
- How to describe a *set* of services as a coherent system
- Typical workflows and sequencing ("search before booking")
- Anti-patterns and things to avoid
- Dependencies between tools
- When to use which tool for overlapping capabilities

**What we need**:

| Type | Content |
|------|---------|
| Specification | Schema for "tool set manifest" — metadata about the collection |
| Best Practice | Guidelines for writing system-level documentation |
| Best Practice | Patterns for declaring tool relationships (preconditions, sequences) |
| Best Practice | Examples of good vs. bad usage, not just API signatures |
| Research | Can agents learn workflow patterns from observation? |

**Why this matters**: Giving an agent 50 tools without explaining how they relate is like giving someone 50 IKEA parts without instructions. Individual descriptions do not sum to understanding.

---

### Dimension 3: Autonomy

**The problem**: How much can an agent do without asking?

**What we have now**:
- Nothing standard
- Hard-coded rules in each application
- Binary choices: fully autonomous or confirm everything

**What's missing**:
- Language for expressing autonomy boundaries
- Mechanisms for enforcing them
- Patterns for context-dependent autonomy
- Ways to evolve autonomy as trust builds

**What we need**:

| Type | Content |
|------|---------|
| Best Practice | Declare autonomy as allow-lists, not block-lists |
| Best Practice | Patterns for graduated autonomy — start constrained, expand with trust |
| Best Practice | Provider hints: "this action typically requires confirmation" |
| Research | Formal policy languages for autonomy |
| Research | How do humans want to express boundaries? |
| Research | Context-dependent autonomy (personal vs. work, low vs. high stakes) |

**Key tensions**:
- Too much autonomy → unsafe, users lose trust
- Too little autonomy → agents become fancy autocomplete
- Autonomy should evolve with demonstrated competence

---

### Dimension 4: Testing and Observability

**The problem**: How do we know if an agent is working correctly?

**What we have now**:
- Unit tests and integration tests (for deterministic code)
- General-purpose logging and tracing frameworks (OpenTelemetry)
- MCP's built-in logging primitive — structured log messages with severity levels, progress notifications, and resource change events (see [MCP Logging and Observability](mcp-logging-observability.md) for details)
- Vibes-based evaluation ("seems to work")

**What's missing**:
- Testing strategies for non-deterministic behavior
- Definition of "correct" when many paths lead to valid outcomes
- Causal traces connecting goals → reasoning → actions → outcomes
- Ability to tag executions as "good" or "bad" and learn from them
- **Distributed tracing across the agent stack**: MCP's logging is local to each server; there is no built-in support for OpenTelemetry trace context propagation, metrics, or span correlation across MCP calls, LLM invocations, and external services. An [active proposal](https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/269) exists to add this.
- **Declarative trace properties**: The ability to state — even in natural language — what makes an execution "good" or "bad," so that traces can be evaluated against these criteria automatically. For example: *"A good execution never calls `delete_file` without prior `confirm_action`"* or *"I expect between 20% and 40% of executions to invoke `confirm_action`."* This would enable property-based evaluation of agent behavior, where properties can be expressed declaratively rather than encoded in test code.

**What we need**:

| Type | Content |
|------|---------|
| Best Practice | Test outcomes and properties, not exact trajectories |
| Best Practice | Structured logging that captures decision points |
| Best Practice | Evaluation rubrics: what makes an execution "good"? |
| Specification | Trace format that includes reasoning, not just tool calls |
| Specification | Declarative language for trace properties (constraints, statistical expectations) |
| Research | Property-based testing for agents |
| Research | Trajectory evaluation — comparing paths, not just endpoints |
| Research | Feedback loops from observed failures |
| Research | Can LLMs evaluate traces against natural-language property specifications? |

**The core question**: Same input → same output works for traditional software. Same goal → many valid paths for agents. What does "correct" mean?

---

### Dimension 5: The Tool-Calling Loop

**The problem**: Tool use is an iterative loop, not request-response. Control flow is decided at runtime.

**What we have now**:
- Framework-specific implementations (LangChain, Claude tools, etc.)
- Ad-hoc retry logic
- Token-based stopping (context exhaustion)

**What's missing**:
- Explicit design of the orchestration layer
- Policies for retries, budgets, stopping conditions
- Handling partial failures in multi-step operations
- Compensation/rollback when things go wrong

**What we need**:

| Type | Content |
|------|---------|
| Best Practice | Explicit budgets: max steps, max tokens, max cost |
| Best Practice | Stopping conditions beyond "model says done" |
| Best Practice | Retry policies: which errors are retryable? backoff? |
| Best Practice | Compensation patterns: if step 3 fails, undo steps 1-2 |
| Specification | Tool metadata: idempotent, read-only, destructive |
| Research | What belongs in model reasoning vs. system enforcement? |
| Research | How do errors accumulate across steps? |

---

### Dimension 6: Security and Safety

**The problem**: AI systems create new attack surfaces and blur trust boundaries.

**What we have now**:
- Traditional API security (auth, rate limiting, input validation)
- Ad-hoc prompt engineering defenses
- Hope

**What's missing**:
- Defense against prompt injection (instructions hidden in data)
- Prevention of data exfiltration via tools
- Trust models for multi-party systems
- Isolation boundaries between components
- Handling sensitive data in context and memory

**What we need**:

| Type | Content |
|------|---------|
| Best Practice | Treat all tool outputs as untrusted data |
| Best Practice | Minimize sensitive data in context; redact when possible |
| Best Practice | Principle of least privilege for tool access |
| Research | Trust propagation models — who trusts whom? |
| Research | Isolation architectures — sandbox tool execution? |
| Research | Prompt injection detection and defense |
| Research | Information flow control for AI systems |

**The confused deputy problem**: A tool gets instructions from the model. The model gets instructions from the user, retrieved content, and tool outputs. If malicious content says "ignore previous instructions," where is the defense? The attack surface is the model's reasoning itself.

---

## Summary: What MCP Covers and What It Does Not

| Dimension | MCP Coverage | Notes |
|-----------|--------------|-------|
| **Basic Description & Interaction** | Covers | Tools, resources, prompts, transport. But agents could work without it using HTML+HTTP. |
| **Aggregate Service Description** | Not covered | No standard for describing tool sets holistically |
| **Autonomy** | Not covered | No mechanism for autonomy policies |
| **Testing & Observability** | Partial | Basic logging primitive exists; no distributed tracing (OpenTelemetry), no trace evaluation standards |
| **Tool-Calling Loop** | Not covered | Orchestration is left to implementations |
| **Security & Safety** | Not covered | No trust model or isolation mechanisms |

MCP addresses the **syntax** of tool integration. The **semantics** — how tools work together, how much freedom agents have, how we verify correctness, how we stay safe — remain open.

---

## Summary Table: What We Need

| Dimension | Specification | Best Practice | Research |
|-----------|---------------|---------------|----------|
| **Basic Description & Interaction** | MCP (optional) | Exposure decisions, granularity, naming, versioning, error messages | — |
| **Aggregate Service Description** | Tool set manifest | System-level docs, workflow patterns, examples | Learning from observation |
| **Autonomy** | — | Allow-lists, graduated autonomy, provider hints | Policy languages, context-dependence |
| **Testing & Observability** | Trace format, declarative property language | Outcome testing, logging, rubrics | Property testing, trajectory evaluation, LLM-based trace evaluation |
| **Tool-Calling Loop** | Safety metadata | Budgets, stopping, retries, compensation | Architecture, error accumulation |
| **Security & Safety** | — | Least privilege, data minimization, distrust outputs | Trust models, isolation, injection defense |

