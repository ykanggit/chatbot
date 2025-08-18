from __future__ import annotations

import threading
import logging
import uuid
from pathlib import Path
from typing import Optional, Sequence, cast

from theflow.settings import settings as flowsettings

from kotaemon.base import BaseComponent, Document, RetrievedDocument
from kotaemon.embeddings import BaseEmbeddings
from kotaemon.storages import BaseDocumentStore, BaseVectorStore

from .base import BaseIndexing, BaseRetrieval
from .rankings import BaseReranking, LLMReranking

logger = logging.getLogger(__name__)


VECTOR_STORE_FNAME = "vectorstore"
DOC_STORE_FNAME = "docstore"


class VectorIndexing(BaseIndexing):
    """Ingest the document, run through the embedding, and store the embedding in a
    vector store.

    This pipeline supports the following set of inputs:
        - List of documents
        - List of texts
    """

    cache_dir: Optional[str] = getattr(flowsettings, "KH_CHUNKS_OUTPUT_DIR", None)
    vector_store: BaseVectorStore
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    count_: int = 0

    def to_retrieval_pipeline(self, *args, **kwargs):
        """Convert the indexing pipeline to a retrieval pipeline"""
        return VectorRetrieval(
            vector_store=self.vector_store,
            doc_store=self.doc_store,
            embedding=self.embedding,
            **kwargs,
        )

    def write_chunk_to_file(self, docs: list[Document]):
        # save the chunks content into markdown format
        if self.cache_dir:
            file_name = docs[0].metadata.get("file_name")
            if not file_name:
                return

            file_name = Path(file_name)
            for i in range(len(docs)):
                markdown_content = ""
                if "page_label" in docs[i].metadata:
                    page_label = str(docs[i].metadata["page_label"])
                    markdown_content += f"Page label: {page_label}"
                if "file_name" in docs[i].metadata:
                    filename = docs[i].metadata["file_name"]
                    markdown_content += f"\nFile name: {filename}"
                if "section" in docs[i].metadata:
                    section = docs[i].metadata["section"]
                    markdown_content += f"\nSection: {section}"
                if "type" in docs[i].metadata:
                    if docs[i].metadata["type"] == "image":
                        image_origin = docs[i].metadata["image_origin"]
                        image_origin = f'<p><img src="{image_origin}"></p>'
                        markdown_content += f"\nImage origin: {image_origin}"
                if docs[i].text:
                    markdown_content += f"\ntext:\n{docs[i].text}"

                with open(
                    Path(self.cache_dir) / f"{file_name.stem}_{self.count_+i}.md",
                    "w",
                    encoding="utf-8",
                ) as f:
                    f.write(markdown_content)

    def add_to_docstore(self, docs: list[Document]):
        if self.doc_store:
            print("Adding documents to doc store")
            self.doc_store.add(docs)

    def add_to_vectorstore(self, docs: list[Document]):
        # in case we want to skip embedding
        if self.vector_store:
            print(f"Getting embeddings for {len(docs)} nodes")
            embeddings = self.embedding(docs)
            print("Adding embeddings to vector store")
            self.vector_store.add(
                embeddings=embeddings,
                ids=[t.doc_id for t in docs],
            )

    def run(self, text: str | list[str] | Document | list[Document]):
        input_: list[Document] = []
        if not isinstance(text, list):
            text = [text]

        for item in cast(list, text):
            if isinstance(item, str):
                input_.append(Document(text=item, id_=str(uuid.uuid4())))
            elif isinstance(item, Document):
                input_.append(item)
            else:
                raise ValueError(
                    f"Invalid input type {type(item)}, should be str or Document"
                )

        self.add_to_vectorstore(input_)
        self.add_to_docstore(input_)
        self.write_chunk_to_file(input_)
        self.count_ += len(input_)


class VectorRetrieval(BaseRetrieval):
    """Retrieve list of documents from vector store"""

    vector_store: BaseVectorStore
    # Optional: allow passing collection names from UI when backend supports multiple collections
    collection_name: str | None = None
    doc_store: Optional[BaseDocumentStore] = None
    embedding: BaseEmbeddings
    rerankers: Sequence[BaseReranking] = []
    top_k: int = 5
    first_round_top_k_mult: int = 10
    retrieval_mode: str = "hybrid"  # vector, text, hybrid

    def _filter_docs(
        self, documents: list[RetrievedDocument], top_k: int | None = None
    ):
        if top_k:
            documents = documents[:top_k]
        return documents

    def run(
        self, text: str | Document, top_k: Optional[int] = None, **kwargs
    ) -> list[RetrievedDocument]:
        """Retrieve a list of documents from vector store

        Args:
            text: the text to retrieve similar documents
            top_k: number of top similar documents to return

        Returns:
            list[RetrievedDocument]: list of retrieved documents
        """
        if top_k is None:
            top_k = self.top_k

        # DEBUG: print collection name/index coming from UI/settings and actual backend collection
        try:
            backend_collection = getattr(self.vector_store, "_collection", None)
            backend_collection_name = getattr(backend_collection, "name", None)
        except Exception:
            backend_collection_name = None

        # Derive docstore collection/index name robustly across implementations
        docstore_collection_name = None
        try:
            ds = self.doc_store
            if ds is not None:
                # Common attributes across docstores:
                # - LanceDBDocumentStore: collection_name
                # - ElasticsearchDocumentStore: index_name
                # - SimpleFileDocumentStore: _collection_name
                docstore_collection_name = (
                    getattr(ds, "collection_name", None)
                    or getattr(ds, "index_name", None)
                    or getattr(ds, "_collection_name", None)
                )
                if docstore_collection_name is None:
                    # As a last resort, look for an underlying collection object
                    ds_collection = getattr(ds, "_collection", None)
                    docstore_collection_name = getattr(ds_collection, "name", None)
        except Exception:
            pass

        # collection_name can be provided via UI/settings and passed through when constructing this component
        if self.collection_name or backend_collection_name or docstore_collection_name:
            # Try to derive vector store info (path, collection)
            try:
                vs_collection_name = (
                    getattr(self.vector_store, "_collection_name", None)
                    or backend_collection_name
                )
                vs_path = (
                    getattr(self.vector_store, "_path", None)
                    or getattr(self.vector_store, "path", None)
                )
            except Exception:
                vs_collection_name = backend_collection_name
                vs_path = None

            # Try to derive docstore path
            try:
                ds = self.doc_store
                ds_path = None
                if ds is not None:
                    ds_path = getattr(ds, "db_uri", None) or getattr(ds, "_path", None)
            except Exception:
                ds_path = None

            print(
                f"[info] Using vector store: cls={type(self.vector_store).__name__} "
                f"path={vs_path} (collection={vs_collection_name})"
            )
            print(
                f"[info] Using doc store:    cls={type(self.doc_store).__name__ if self.doc_store else None} "
                f"path={ds_path} (collection={docstore_collection_name})"
            )
            # Keep original concise line
            print(
                f"[VectorRetrieval] Using collection: declared={self.collection_name} "
                f"backend={backend_collection_name} "
                f"docstore={docstore_collection_name}"
            )
            # If LanceDB is used for docstore, list tables and sample a row
            try:
                if ds_path:
                    import lancedb  # type: ignore

                    _db = lancedb.connect(str(ds_path))
                    tbls = _db.table_names()
                    print(f"[diag] LanceDB tables at {ds_path}: {tbls}")
                    if docstore_collection_name in tbls:
                        print(f"[diag] Docstore collection '{docstore_collection_name}' exists.")
                    for t in tbls[:3]:
                        try:
                            table = _db.open_table(t)
                            sample = table.search().limit(1).to_list()
                            print(f"[diag] Table '{t}' sample row: {sample[0] if sample else '<empty>'}")
                        except Exception as e:
                            print(f"[diag] Could not sample table '{t}': {e}")
            except Exception as e:
                print(f"[diag] Could not inspect LanceDB docstore: {e}")

        # Optional diagnostics: attempt to count vectors in the vector store
        try:
            cnt_fn = getattr(self.vector_store, "count", None)
            if callable(cnt_fn):
                _vs_count = cnt_fn()
                print(f"[diag] Vector store count: {_vs_count}")
                if _vs_count == 0:
                    # If Chroma is used and path is known, list collections for hints
                    try:
                        import chromadb  # type: ignore

                        _vs_path = (
                            getattr(self.vector_store, "_path", None)
                            or getattr(self.vector_store, "path", None)
                        )
                        if _vs_path:
                            _client = chromadb.PersistentClient(path=str(_vs_path))
                            cols = _client.list_collections()
                            names = [getattr(c, "name", "unknown") for c in cols]
                            print(f"[diag] Found {len(cols)} Chroma collections at path={_vs_path}: {names}")
                            for c in cols[:5]:
                                try:
                                    print(f"[diag] Collection '{getattr(c, 'name', 'unknown')}' count: {c.count()}")
                                except Exception as e:
                                    print(f"[diag] Could not count collection '{getattr(c, 'name', 'unknown')}': {e}")
                            # Show a quick directory listing
                            try:
                                from pathlib import Path as _Path

                                entries = [str(p) for p in list(_Path(_vs_path).glob('*'))[:10]]
                                print(f"[diag] Vectorstore directory entries (first 10): {entries}")
                            except Exception as e:
                                print(f"[diag] Could not list vectorstore directory: {e}")
                    except Exception as e:
                        print(f"[diag] Could not list Chroma collections: {e}")
        except Exception as e:
            print(f"[diag] Could not count vector store: {e}")

        # Optionally disable metadata filters before querying vector store.
        # Ways to enable:
        #  - Pass one of these kwargs to VectorRetrieval.run(...):
        #      disable_filters=True | ignore_filters=True | disable_metadata_filters=True
        #  - Or set in flowsettings.py: KH_DISABLE_VECTOR_FILTERS = True
        try:
            disable_filters = (
                bool(kwargs.pop("disable_filters", False))
                or bool(kwargs.pop("ignore_filters", False))
                or bool(kwargs.pop("disable_metadata_filters", False))
                or bool(getattr(flowsettings, "KH_DISABLE_VECTOR_FILTERS", False))
            )
        except Exception:
            disable_filters = False

        if disable_filters and "filters" in kwargs:
            removed_filters = kwargs.pop("filters", None)
            print(f"[diag] Metadata filters disabled; removed filters={removed_filters}")

        do_extend = kwargs.pop("do_extend", False)
        thumbnail_count = kwargs.pop("thumbnail_count", 3)

        if do_extend:
            top_k_first_round = top_k * self.first_round_top_k_mult
        else:
            top_k_first_round = top_k

        if self.doc_store is None:
            raise ValueError(
                "doc_store is not provided. Please provide a doc_store to "
                "retrieve the documents"
            )

        result: list[RetrievedDocument] = []
        # TODO: should declare scope directly in the run params
        scope = kwargs.pop("scope", None)
        emb: list[float]

        if self.retrieval_mode == "vector":
            print(f'Creating embedding for text: {text}, top_k: {top_k_first_round}, scope: {scope}, vectorstore: {type(self.vector_store).__name__}')
            logger.info(f'Creating embedding for text: {text}, top_k: {top_k_first_round}, scope: {scope}')
            emb = self.embedding(text)[0].embedding
            try:
                print(f"[diag] Query embedding length: {len(emb)}")
                print(f"[diag] Query embedding preview (first 8): {emb[:8]}")
            except Exception:
                pass
            print(f"[diag] Vector store query kwargs preview: scope_len={len(scope) if scope else 0}, do_extend={do_extend}, top_k_first_round={top_k_first_round}")
            # Optional: introspect underlying Chroma collection
            try:
                _collection = getattr(self.vector_store, "_collection", None)
                if _collection is not None:
                    print(f"[diag] Chroma collection name: {getattr(_collection, 'name', 'unknown')}")
                    try:
                        print(f"[diag] Chroma collection count: {_collection.count()}")
                    except Exception as e:
                        print(f"[diag] Could not count via collection.count(): {e}")
                    try:
                        sample = _collection.get(limit=3)
                        _ids = sample.get("ids", [])
                        _mds = sample.get("metadatas", [])
                        print(f"[diag] Sample ids (up to 3): {_ids}")
                        print(f"[diag] Sample metadata (up to 3): {_mds}")
                        try:
                            emb_sample = _collection.get(limit=1, include=['embeddings'])
                            _embs = emb_sample.get('embeddings', None)
                            dim = None
                            if _embs is not None:
                                try:
                                    # Case: list/tuple of vectors
                                    if isinstance(_embs, (list, tuple)):
                                        if len(_embs) > 0 and _embs[0] is not None:
                                            vec0 = _embs[0]
                                            dim = len(vec0) if hasattr(vec0, '__len__') else None
                                    # Case: numpy array or similar (e.g., shape (1, D) or (D,))
                                    elif hasattr(_embs, 'shape'):
                                        shape = getattr(_embs, 'shape', None)
                                        if shape:
                                            dim = shape[-1] if len(shape) >= 1 else None
                                except Exception:
                                    dim = None
                            if dim is not None:
                                print(f"[diag] Collection embedding dimension: {dim}")
                            else:
                                print(f"[diag] Embeddings present but could not determine dimension; type={type(_embs)}")
                        except Exception as e:
                            print(f"[diag] Could not fetch embeddings to determine dimension: {e}")
                    except Exception as e:
                        print(f"[diag] Could not fetch sample from Chroma: {e}")
                else:
                    print("[diag] Could not access underlying Chroma collection object on vector store.")
            except Exception as e:
                print(f"[diag] Error introspecting Chroma collection: {e}")
            # Print exact kwargs before querying vector store
            try:
                _query_kwargs = {"top_k": top_k_first_round, "doc_ids": scope, **kwargs}
                _safe_query_kwargs = {k: v for k, v in _query_kwargs.items() if k != "embedding"}
                print(f"[diag] vector_store.query kwargs: {_safe_query_kwargs}")
                print(f"[diag] vector_store.query embedding_len={len(emb)}")
            except Exception:
                pass
            _, scores, ids = self.vector_store.query(
                embedding=emb, top_k=top_k_first_round, doc_ids=scope, **kwargs
            )
            docs = self.doc_store.get(ids)
            logger.info(f'Retrieved {len(docs)} documents from vector store')
            print(f'Retrieved {len(docs)} documents from vector store')
            result = [
                RetrievedDocument(**doc.to_dict(), score=score)
                for doc, score in zip(docs, scores)
            ]
        elif self.retrieval_mode == "text":
            query = text.text if isinstance(text, Document) else text
            docs = []
            if scope:
                docs = self.doc_store.query(
                    query, top_k=top_k_first_round, doc_ids=scope
                )
            result = [RetrievedDocument(**doc.to_dict(), score=-1.0) for doc in docs]
        elif self.retrieval_mode == "hybrid":
            # similarity search section
            emb = self.embedding(text)[0].embedding
            try:
                print(f"[diag] Query embedding length: {len(emb)}")
                print(f"[diag] Query embedding preview (first 8): {emb[:8]}")
            except Exception:
                pass
            vs_docs: list[RetrievedDocument] = []
            vs_ids: list[str] = []
            vs_scores: list[float] = []

            def query_vectorstore():
                nonlocal vs_docs
                nonlocal vs_scores
                nonlocal vs_ids

                assert self.doc_store is not None
                print(f"[diag] Vector store query kwargs preview: scope_len={len(scope) if scope else 0}, do_extend={do_extend}, top_k_first_round={top_k_first_round}")
                try:
                    _query_kwargs = {"top_k": top_k_first_round, "doc_ids": scope, **kwargs}
                    _safe_query_kwargs = {k: v for k, v in _query_kwargs.items() if k != "embedding"}
                    print(f"[diag] vector_store.query kwargs: {_safe_query_kwargs}")
                    print(f"[diag] vector_store.query embedding_len={len(emb)}")
                except Exception:
                    pass
                _, vs_scores, vs_ids = self.vector_store.query(
                    embedding=emb, top_k=top_k_first_round, doc_ids=scope, **kwargs
                )
                if vs_ids:
                    vs_docs = self.doc_store.get(vs_ids)

            # full-text search section
            ds_docs: list[RetrievedDocument] = []

            def query_docstore():
                nonlocal ds_docs

                assert self.doc_store is not None
                query = text.text if isinstance(text, Document) else text
                if scope:
                    ds_docs = self.doc_store.query(
                        query, top_k=top_k_first_round, doc_ids=scope
                    )

            vs_query_thread = threading.Thread(target=query_vectorstore)
            ds_query_thread = threading.Thread(target=query_docstore)

            vs_query_thread.start()
            ds_query_thread.start()

            vs_query_thread.join()
            ds_query_thread.join()

            result = [
                RetrievedDocument(**doc.to_dict(), score=-1.0)
                for doc in ds_docs
                if doc not in vs_ids
            ]
            result += [
                RetrievedDocument(**doc.to_dict(), score=score)
                for doc, score in zip(vs_docs, vs_scores)
            ]
            print(f"Got {len(vs_docs)} from vectorstore")
            print(f"Got {len(ds_docs)} from docstore")

        # use additional reranker to re-order the document list
        if self.rerankers and text:
            for reranker in self.rerankers:
                # if reranker is LLMReranking, limit the document with top_k items only
                if isinstance(reranker, LLMReranking):
                    result = self._filter_docs(result, top_k=top_k)
                result = reranker.run(documents=result, query=text)

        result = self._filter_docs(result, top_k=top_k)
        print(f"Got raw {len(result)} retrieved documents")

        # add page thumbnails to the result if exists
        thumbnail_doc_ids: set[str] = set()
        # we should copy the text from retrieved text chunk
        # to the thumbnail to get relevant LLM score correctly
        text_thumbnail_docs: dict[str, RetrievedDocument] = {}

        non_thumbnail_docs = []
        raw_thumbnail_docs = []
        for doc in result:
            if doc.metadata.get("type") == "thumbnail":
                # change type to image to display on UI
                doc.metadata["type"] = "image"
                raw_thumbnail_docs.append(doc)
                continue
            if (
                "thumbnail_doc_id" in doc.metadata
                and len(thumbnail_doc_ids) < thumbnail_count
            ):
                thumbnail_id = doc.metadata["thumbnail_doc_id"]
                thumbnail_doc_ids.add(thumbnail_id)
                text_thumbnail_docs[thumbnail_id] = doc
            else:
                non_thumbnail_docs.append(doc)

        linked_thumbnail_docs = self.doc_store.get(list(thumbnail_doc_ids))
        print(
            "thumbnail docs",
            len(linked_thumbnail_docs),
            "non-thumbnail docs",
            len(non_thumbnail_docs),
            "raw-thumbnail docs",
            len(raw_thumbnail_docs),
        )
        additional_docs = []

        for thumbnail_doc in linked_thumbnail_docs:
            text_doc = text_thumbnail_docs[thumbnail_doc.doc_id]
            doc_dict = thumbnail_doc.to_dict()
            doc_dict["_id"] = text_doc.doc_id
            doc_dict["content"] = text_doc.content
            doc_dict["metadata"]["type"] = "image"
            for key in text_doc.metadata:
                if key not in doc_dict["metadata"]:
                    doc_dict["metadata"][key] = text_doc.metadata[key]

            additional_docs.append(RetrievedDocument(**doc_dict, score=text_doc.score))

        result = additional_docs + non_thumbnail_docs

        if not result:
            # return output from raw retrieved thumbnails
            result = self._filter_docs(raw_thumbnail_docs, top_k=thumbnail_count)

        try:
            print(f"[result] Retrieved {len(result)} results:")
            for i, doc in enumerate(result, 1):
                try:
                    text_val = getattr(doc, "text", None) or getattr(doc, "content", "") or ""
                except Exception:
                    text_val = ""
                snippet = (text_val[:280] + "...") if isinstance(text_val, str) and len(text_val) > 280 else text_val
                file_name = doc.metadata.get("file_name", "")
                page = doc.metadata.get("page_label", "")
                print("-" * 80)
                print(f"[{i}] id={doc.doc_id} score={getattr(doc, 'score', None)} file_name={file_name} page={page}")
                print(snippet)
        except Exception as e:
            print(f"[diag] Could not print results summary: {e}")

        return result


class TextVectorQA(BaseComponent):
    retrieving_pipeline: BaseRetrieval
    qa_pipeline: BaseComponent

    def run(self, question, **kwargs):
        retrieved_documents = self.retrieving_pipeline(question, **kwargs)
        return self.qa_pipeline(question, retrieved_documents, **kwargs)

