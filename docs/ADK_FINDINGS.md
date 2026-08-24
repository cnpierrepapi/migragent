# Things that bit us in ADK

Kept because building on a thing is the only way to find the parts that are wrong, and because
these should go back to `google/adk-python` rather than sit in our code comments forever.

Version: `google-adk` 2.7.1, August 2026. Every one of these cost real time here.

Field names in 1 and 2 were checked against `GenerateContentConfig` on google-genai 2.x field by
field, not remembered. The type carries 35 fields and they go to three different places: 6 at the
top level of a Vertex request, 3 that mean something only to the client library, and 26 sampling
settings that belong inside `generationConfig`.

## 1. A wrong config split silently drops your tools

The one that hurt most.

ADK hands a custom `BaseLlm` an `LlmRequest` whose `config` mixes two kinds of thing. Sampling
settings like temperature and `maxOutputTokens` belong inside `generationConfig` on the wire.
Tools, `systemInstruction` and `safetySettings` sit at the top level of a Vertex
`generateContent` request.

Put them all in `generationConfig` and nothing raises. The call succeeds. You get a normal looking
response. The tools are just gone, so your agent has no tools and cheerfully answers from memory
instead of calling anything.

We lost a while to that. The agent looked like it was refusing to use its tools, and we went
looking for a prompt problem, because a prompt problem is what "the model won't call the tool"
usually means.

The fix on our side is a named list rather than a guess:

```python
TOP_LEVEL = {"tools", "toolConfig", "systemInstruction", "safetySettings",
             "cachedContent", "labels"}
```

Those six are the complete top level set on google-genai 2.x.

What would help upstream: either a documented mapping from `LlmRequest.config` to the REST shape,
or a helper that does the split. Right now every custom `BaseLlm` has to rediscover it, and the
failure is silent, which is the worst kind.

## 2. Client-only fields get sent to the wire and rejected

Same area, smaller bite. `LlmRequest.config` carries fields that mean something to the genai
client library and nothing to the REST endpoint. There are three: `httpOptions`,
`automaticFunctionCalling`, `shouldReturnHttpResponse`.

Forward them and Vertex rejects the request as having unknown fields. So a custom `BaseLlm` has to
know which parts of the config are for the library and which are for the server, and nothing says
which is which.

Ours:

```python
NOT_FOR_THE_WIRE = {"httpOptions", "automaticFunctionCalling",
                    "shouldReturnHttpResponse"}
```

An earlier version of this note also listed `abortSignal` and `retryOptions`, and both were wrong.
`abortSignal` is not a field on `GenerateContentConfig` at all. `retryOptions` is real but it sits
inside `HttpOptions`, so dropping `httpOptions` already takes it along. Neither mistake could
change behaviour, because a field that never appears can never be forwarded, which is exactly why
it survived. Worth saying out loud: this list was written from watching things fail, and a list
written that way records what you saw, not what is there. Checking it against the type took two
minutes and should have happened first.

## 3. Closing an event stream early prints a traceback for a non-error

Stop an ADK run before the agent finishes and OpenTelemetry tries to unwind a span in a context it
was not opened in. You get a traceback in your logs for something you chose to do.

We stop early on purpose. There is a page budget and a turn cap, and hitting either is a normal
outcome, not a crash. But a job log full of tracebacks is a job log nobody reads, and the whole
point of the log is that somebody can audit the run.

The workaround is to iterate the stream by hand instead of with `async for`, so the close happens
inside the coroutine that opened it:

```python
try:
    while True:
        try:
            event = await events.__anext__()
        except StopAsyncIteration:
            break
        ...
finally:
    await events.aclose()
```

That is more code than it should be for "stop the agent". A supported cancel would be better.

## 4. Installing it moves your other Google pins

`google-adk` 2.7.1 pulled `google-auth` from 2.30.0 up to 2.56.3, which pulled
`google-cloud-firestore` and `google-cloud-storage` with it. Our deploy failed on the version
skew, not on anything we wrote.

This one is ordinary dependency life and not really a bug. Worth writing down because the failure
appears at deploy time in a service that had nothing to do with the agent, and it reads like an
unrelated regression until you check what changed. Logged as D33.

## What to do with these

Numbers 1 and 2 are the same underlying gap: the boundary between `LlmRequest.config` and a Vertex
request body is undocumented, and getting it wrong fails quietly. That is one good issue with a
reproduction, and possibly one small PR.

Number 3 is its own thing and needs a maintainer's opinion on whether early cancellation is meant
to be supported. Posted as a comment on `google/adk-python#2792` on 22 Aug, with a design for the
cancel API on `#2425` the same day. Neither has a reply yet.

Per the contribution plan: hit the problem while using the thing, write it up so it leaves nothing
to search for, quantify it, and never shop an issue tracker for something to fix.
