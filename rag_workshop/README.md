<!-- Copyright Vespa.ai. Licensed under the terms of the Apache 2.0 license. See LICENSE in the project root.-->

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://assets.vespa.ai/logos/Vespa-logo-green-RGB.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://assets.vespa.ai/logos/Vespa-logo-dark-RGB.svg">
  <img alt="#Vespa" width="200" src="https://assets.vespa.ai/logos/Vespa-logo-dark-RGB.svg" style="margin-bottom: 25px;">
</picture>


# Vespa.ai RAG Application Workshop

Vespa.ai is an AI application platform with an extensive history that started at Yahoo. It powers some of the world’s largest and most demanding solutions including Yahoo itself, Perplexity, BigData.com, and Vinted. This long-standing ( 25+ years) evolution has culminated in a robust system that supports large-scale search and recommendation applications.

Please visit our [Blog](https://blog.vespa.ai/) to learn more about ML/AI and how to move it into production.


# Workshop preparation 
Before we start our workshop it is required that you clone this [repository](https://github.com/vespaai/university/tree/main/rag_workshop)

<pre>
git clone https://vespaai/university/university.git
</pre>

What you will find in this repository:
  - [workshop](https://github.com/vespaai/university/tree/main/rag_workshop/rag) - rag application which you will need to modify and deploy


Assuming that prerequisites are met, you have been able to deploy "news" application and you have access to the [Vespa Cloud](https://cloud.vespa.ai/) you can continue with the lab. 


# What is a Vespa Application?

A [Vespa application](https://docs.vespa.ai/en/application-packages.html) is a complete package that includes document schemas, service definitions, search chains, and integrations for features like embeddings and LLM-based processing.
Two key configuration files form the backbone of any Vespa application:
	•	[schema.sd](https://docs.vespa.ai/en/schemas.html): Defines the document schema including fields, indexing,  embedder configurations, rankers specifications and other configurations.
	•	[services.xml](https://docs.vespa.ai/en/reference/services.html): Specifies the deployment details and the Vespa services (container, search, document processing, etc.) definitiona and configuration.

# Embedding 
A common technique is to map unstructured data like text or images to points in an abstract vector space and then do computation in that space. For example, retrieve similar data by finding nearby points in the vector space, or using the vectors as input to a neural net. This mapping is referred to as embedding. Read more about embedding and embedding management in this [blog post](https://blog.vespa.ai/tailoring-frozen-embeddings-with-vespa/). 

# Document schema and embedding Configuration
Schema Definition (schema.sd)

Within your passge.sd file, you’ll define a document schema that includes the [embedding](https://docs.vespa.ai/en/embedding.html) field and rank profile (Ranking profile for RRF raking is showed in the next section).
Please use example below to see how add embedder into your application.

Example:

```javascript
schema passage {
  document passage {
     field id type string {
      indexing: summary | attribute
    }
    field text type string {
      indexing: summary | index
      index: enable-bm25
    }
  }

  #field generated during ingest phase, notice its outside of the document specification
  #embed embedder_name runs embedding on the field text, it has to be specified inside services.xml file

  field embedding type tensor<float>(x[384]) {
    indexing {
      ( input text || "" ) | embed e5 | attribute | index # Index keyword enables HNSW index
    }
    attribute {
      distance-metric: angular #match the E5 embedding model distance metric
    }
  }

  fieldset default {
    fields: text
  }

  rank-profile default {
    first-phase {
      expression {
        bm25(text)
      }
    }
 }

}
```

# Hybrid RRF Ranking

The [ranking](https://docs.vespa.ai/en/ranking.html) configuration is crucial for delivering relevant results. Vespa supports a novel staged rankig with custom expressions. 
In this lab we will focus on Hybrid RRF ranking approach which combines vector similarity with traditional lexical ranking (bm25). 

Within your schema configuration , you would configure a profile like:

```javascript
  rank-profile closeness {
    inputs {
      query(q_embedding) tensor<float>(x[384])
    }
    first-phase {
      expression: closeness(field, embedding)
    }
  }

  rank-profile rrf inherits closeness {
    function best_bm25() {
          expression: bm25(text)
      }

      global-phase {
          rerank-count: 200
          expression: reciprocal_rank(closeness(field, embedding)) + reciprocal_rank(best_bm25())
      }
  }
```

The expression closeness(embedding, q_embedding) is used to compute the similarity between the document embedding and the query embedding (q_embedding).

Additional scoring functions can be combined to refine the ranking further.


# Service Definition (services.xml)

In the [services.xml](https://docs.vespa.ai/en/reference/services.html), you configure container components like embedder, llm clients and define search chains. In the downloaded application package you will find placeholders for each of the components.

# Embedding Configuration
To enable embedding generation, you need to configure the embedder in the services.xml file. This example defines an E5 embedder from Huggingface. Vespa supports multiple embedding models. See [embedding documentation](https://docs.vespa.ai/en/embedding.html) for more details.

```xml
    <component id="e5" type="hugging-face-embedder">
        <transformer-model url="https://github.com/vespa-engine/sample-apps/raw/master/simple-semantic-search/model/e5-small-v2-int8.onnx"/>
        <tokenizer-model url="https://raw.githubusercontent.com/vespa-engine/sample-apps/master/simple-semantic-search/model/tokenizer.json"/>
        <prepend> <!-- E5 prompt instructions -->
            <query>query:</query>
            <document>passage:</document>
        </prepend>
    </component>
```
Once finished base configuration lets test it!

# Testing - Application Deployment
Once you have configured the embedding you can deploy your application.
```bash
vespa deploy --wait 120
```
# Testing - Data Feeding
To feed your data into Vespa, you can use the vespa feed command.
```bash
vespa feed ext/docs.jsonl
```

# Testing semantic basic search and RRF ranking

Once you have deployed your application and fed your data, test your semantic search with a command:

```bash
vespa query \
    --timeout 120 \
    yql="select * from passage where ({targetHits:1000}nearestNeighbor(embedding,q_embedding))"\
    ranking.profile=closeness\
    query_text="Medical Tours costa Rica"\
    "input.query(q_embedding)"="embed(@query_text)"
```

If the response meets your expectations, move on to testing the rrf ranking, see that to change ranking we needed only to change ranker name in the parameter:

```bash
vespa query \
    --timeout 120 \
    yql="select * from passage where ({targetHits:1000}nearestNeighbor(embedding,q_embedding))"\
    ranking.profile=rrf\
    query_text="Medical Tours costa Rica"\
    "input.query(q_embedding)"="embed(@query_text)"
```

# Query profile configuration
[Query profiles](https://docs.vespa.ai/en/query-profiles.html) are used to simplify the query language and reduce the number of parameters to be passed to the query.

In your case we will configure "vector-search". you will need to create directory "search/query-profiles" and "search/query-profiles/types "under your "rag"  application directory. 

```bash
mkdir -p search/query-profiles/types
```

Query profile is the file where we specify the query parameters which will be passed to the query.
```bash
vi search/query-profiles/vector-search.xml
```
and fill the content of the file with the following:

```xml
<query-profile id="vector-search" type="vector-search-type">
    <field name="yql">select * from passage where ({targetHits:100}nearestNeighbor(embedding,q_embedding))</field>
    <field name="ranking.profile">closeness</field>
</query-profile>
```
Now you will need to edit vector-search-types.xml file:
```bash
vi search/query-profiles/types/vector-search-type.xml
```
and fill the content of the file with the following:

```xml
<query-profile-type id="vector-search-type">
    <field name="yql" type="string"/>
    <field name="ranking.profile" type="string"/>
    <field name="input.query(q_embedding)" type="tensor&lt;float&gt;(x[384])"/>
    <field name="query_text" type="string"/>
</query-profile-type>
```

# Testing - Application Deployment
Once you have configured the query profile you can deploy your application.
```bash
vespa deploy --wait 120
```

# Query profile configuration testing
  Now you can test your query profile by running the following command:
  ```bash
vespa query \
    --timeout 120 \
    queryProfile=vector-search\
    query_text="Medical Tours costa Rica" \
    ranking.profile="closeness" \
    "input.query(q_embedding)"="embed(@query_text)"
  ```



# LLM Client Configuration
To enable LLM-based processing, you need to configure the LLM client in the services.xml file. This example defines an LLM client from Huggingface. Vespa supports multiple LLM clients. See [LLM documentation](https://docs.vespa.ai/en/llms-in-vespa.html) for more details.


Locally hosted LLM client:
```xml
    <component id="phi" class="ai.vespa.llm.clients.LocalLLM">
      <config name="ai.vespa.llm.clients.llm-local-client">
        <model url="https://data.vespa-cloud.com/gguf_models/llama-3.2-1b-instruct-q8_0.gguf" />
        <contextSize>4096</contextSize>
        <parallelRequests>1</parallelRequests>
      </config>
    </component>
```
OpenAI hosted LLM client:
```xml
    <component id="openai" class="ai.vespa.llm.clients.OpenAI">
      <config name = "ai.vespa.llm.clients.llm-client">
        <apiKeySecretName>openai-api-key</apiKeySecretName>
      </config>
    </component>
```
You will also need to define secret store configuration in the services.xml file.

```xml
    <secrets>
            <apiKey vault="my-vault" name="openai-api-key" />
    </secrets>
```

Note that the OpenAI client requires an API key. Please refer [secret store](https://cloud.vespa.ai/en/security/secret-store) documentation how to add it to your application. You need to enter your personal OpenAI API key to the secret store.

# RAG Search Chain Configuration
In the services.xml file, you define the search chain. The search chain defines the order in which the search components are executed. In this example, the RAG search chains are defined as follows:



RAG Searcher using local inference 

```xml
      <chain id="local" inherits="vespa">
        <searcher id="ai.vespa.search.llm.RAGSearcher">
          <config name="ai.vespa.search.llm.llm-searcher">
            <providerId>phi</providerId>
          </config>
        </searcher>
      </chain>
```

# Provision GPU Node
To run inference fast GPU node has to be provisioned.

```xml
    <nodes count="1" deploy:environment="dev">
      <resources vcpu="4.0" memory="16Gb" architecture="x86_64" storage-type="local" disk="125Gb">
        <gpu count="1" memory="16.0Gb"/>
      </resources>
    </nodes>
```
Make sure this is added to your container section

RAG Searcher using OpenAI LLM client
```xml
     <chain id="openai" inherits="vespa">
        <searcher id="ai.vespa.search.llm.RAGSearcher">
          <config name="ai.vespa.search.llm.llm-searcher">
            <providerId>openai</providerId>
          </config>
        </searcher>
      </chain>
```

# Application Deployment
Once you have configured the embedding and LLM clients, you can deploy your application.
```bash
vespa deploy --wait 120
```


# Testing RAG Searcher

Test query using local LLM inference with contextual RRF retrieval:

```bash
vespa query \
    --timeout 120 \
    queryProfile=vector-search\
    query="Are Medical Tours costa Rica Popular?" \
    hits=5 \
    searchChain=local \
    format=sse \
    "input.query(q_embedding)"="embed(@query)" \
    prompt="@query - Answer to the query in the details, list all the documents provided and its content. See documents below:{context}" \
    traceLevel=1
```

Test query using OpenAI LLM inference with RRF retrieval:
```bash
vespa query \
    --timeout 120 \
    queryProfile=vector-search\
    query_text="manhattan project" \
    query="Are Medical Tours costa Rica Popular?" \
    hits=5 \
    searchChain=openai \
    format=sse \
    "input.query(q_embedding)"="embed(@query_text)" \
    prompt="@query -  Answer to the query in the details, list all the documents provided and its content. See documents below:{context}" \
    traceLevel=1
```

Amazing you finished vespa quick guide! Now look at other vespa examples.


#Vespa additional resources
- Whenever you need to build solution which requires advanced search capability, either AI chatbot, E-Comerce personalised experience or Document search you will find good examples [here](https://github.com/vespa-engine/sample-apps)
- Vespa offers extensive tensor support see [Advent of Tensors](https://blog.vespa.ai/advent-of-tensors-2023/)
- Vespa provides Python API called [PyVespa](https://pyvespa.readthedocs.io/en/latest/index.html)

Thank You!





