# agents/narrative_agent.py
# The Nexus Narrative Agent — Multi-Modal Documentary Synthesizer.
# Ingests multiple URLs + PDFs, runs hybrid RAG, synthesizes a
# documentary-style narrative, and syncs audio with the JARVIS HUD.
#
# Plug-in: drop this file in /agents/ — registry auto-discovers it.
# Dependencies: pip install pymupdf requests beautifulsoup4 pillow
#               langchain-community langchain-huggingface langchain-ollama
#               rank_bm25 faiss-cpu

import io
import os
import re
import logging
from pathlib import Path
from typing import Optional

from agents._base import BaseAgent, AgentInput, AgentOutput
from io_layer.hud import hud
from io_layer.mouth import mouth

logger = logging.getLogger(__name__)

# ── Image filter constants ─────────────────────────────────────
IMG_MIN_WIDTH  = 300
IMG_MIN_HEIGHT = 200
IMG_MIN_ASPECT = 0.9    # skip very tall portrait images
IMG_MAX_ASPECT = 5.5    # skip horizontal banners
IMG_MAX_PER_SOURCE = 3  # max images extracted per URL or PDF


# ─────────────────────────────────────────────────────────────
# NarrativeAgent
# ─────────────────────────────────────────────────────────────

class NarrativeAgent(BaseAgent):
    name = "nexus_agent"
    description = (
        "The primary research and synthesis agent. Use this for ALL queries requiring "
        "web searches, reading URLs, PDF parsing, or deep research into a topic (e.g. 'talk about X', 'research Y'). "
        "It will search the web automatically, extract text and visuals, and generate a documentary-style narrative."
    )
    triggers = [
        "read this", "analyze this", "research",
        "tell me about", "brief me on", "summarize this",
        "nexus", "run nexus", "documentary",
        "http://", "https://", ".pdf",
    ]

    def __init__(self):
        # ── Lazy-loaded — not initialized until first run() call ──
        # Prevents 10-30s boot delay when JARVIS starts up.
        self._llm        = None
        self._embeddings = None

    # ── Lazy loaders ──────────────────────────────────────────

    @property
    def llm(self):
        if self._llm is None:
            logger.info("NarrativeAgent: loading Gemini Flash with Groq fallback...")
            from langchain_google_genai import ChatGoogleGenerativeAI
            from langchain_groq import ChatGroq
            import os
            
            primary_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.3, max_retries=0)
            
            fallback_llm = ChatGroq(
                model="openai/gpt-oss-120b", # Groq's GPT-OSS 120B model
                temperature=0.3,
                api_key=os.environ.get("GROQ_API_KEY")
            )
            
            self._llm = primary_llm.with_fallbacks([fallback_llm])
        return self._llm

    @property
    def embeddings(self):
        if self._embeddings is None:
            logger.info("NarrativeAgent: loading HuggingFace embeddings...")
            from langchain_huggingface import HuggingFaceEmbeddings
            self._embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        return self._embeddings

    # ── Entry point ───────────────────────────────────────────

    def run(self, input: AgentInput) -> AgentOutput:
        # 1. Parse sources from query + context
        urls, pdf_paths = self._parse_sources(input)

        # 2. Ingest all sources
        hud.update_status("Omnivore ingesting sources...")
        all_docs, all_images, all_labels = self._ingest_all(
            input.query, urls, pdf_paths, web_search=(not urls and not pdf_paths)
        )

        if not all_docs:
            return AgentOutput(
                result="I couldn't extract content from the provided sources. Check the URLs or PDF paths.",
                confidence=0.0,
                source=self.name,
            )

        # 3. Hybrid retrieval (BM25 + FAISS + RRF)
        hud.update_status("Running hybrid search...")
        retrieved = self._hybrid_search(input.query, all_docs)

        # 4. Synthesize documentary narrative
        hud.update_status("Synthesizing narrative...")
        script = self._synthesize_narrative(input.query, retrieved, all_labels)

        # 5. Play story — audio + HUD sync, section by section
        clean_script = self._play_cinematic_story(script, all_images, all_labels)

        # 6. Clean up HUD after story ends
        hud.clear()

        return AgentOutput(
            result=clean_script or script,
            confidence=0.9,
            source=self.name,
            requires_voice=False,       # voice handled internally via speak_and_wait
            requires_display=False,     # web UI display is now handled chunk-by-chunk inside _play_cinematic_story

            metadata={
                "sources": len(urls) + len(pdf_paths),
                "images_found": len(all_images),
                "urls": urls,
                "pdf_paths": pdf_paths,
            },
        )

    # ── Source Parser ─────────────────────────────────────────

    # agents/narrative_agent.py

    def _parse_sources(self, input: AgentInput) -> tuple[list[str], list[str]]:
        url_re = re.compile(r'https?://[^\s<>"\']+')
        urls = url_re.findall(input.query)

        pdf_re = re.compile(r'[\w./\\: -]+\.pdf', re.IGNORECASE)
        pdf_paths = [p.strip() for p in pdf_re.findall(input.query) if Path(p.strip()).exists()]

        urls += input.context.get("urls", [])
        pdf_paths += input.context.get("pdf_paths", [])

        if not urls and not pdf_paths:
            logger.info("NexusAgent: No sources detected. Bypassing GUI prompt.")
            # Instead of popping up a blocking GUI window, just let the agent proceed.
            # The agent will handle the empty sources by doing a mock web search or returning a graceful error.

        urls = list(dict.fromkeys(urls))
        pdf_paths = list(dict.fromkeys(pdf_paths))
        return urls, pdf_paths

    def _request_sources_gui(self) -> tuple[list[str], list[str]]:
        """Opens a quick Windows dialog to grab a URL or PDF file."""
        import tkinter as tk
        from tkinter import filedialog, simpledialog, messagebox
        
        # Create a temporary, hidden main window
        root = tk.Tk()
        root.attributes('-topmost', True) # Force the popup to the front of your screen
        root.withdraw()
        
        urls = []
        pdf_paths = []
        
        # Ask the user what type of file they want to ingest
        choice = messagebox.askyesnocancel(
            "Nexus Initialization", 
            "Do you want to analyze a local PDF document?\n\n(Click 'No' to enter a Web URL instead)"
        )
        
        if choice is True: # User clicked Yes -> Open File Browser
            file_path = filedialog.askopenfilename(
                title="Select a PDF for Nexus",
                filetypes=[("PDF Documents", "*.pdf")]
            )
            if file_path:
                pdf_paths.append(file_path)
                
        elif choice is False: # User clicked No -> Open URL Input Box
            url = simpledialog.askstring(
                "Nexus Initialization",
                "Enter the target Web URL:"
            )
            if url:
                # Auto-format the URL if you just paste "wikipedia.org"
                if not url.startswith("http"):
                    url = "https://" + url
                urls.append(url)
                
        root.destroy()
        return urls, pdf_paths

    # ── Ingestion ─────────────────────────────────────────────

    def _ingest_all(
        self,
        query: str,
        urls: list[str],
        pdf_paths: list[str],
        web_search: bool = False,
    ) -> tuple[list, list[bytes], list[str]]:
        """
        Runs all intake channels. Returns:
          - all_docs: list of LangChain Document objects
          - all_images: list of image bytes (PNG)
          - all_labels: list of captions for each image
        """
        from langchain_core.documents import Document

        all_docs   = []
        all_images = []
        all_labels = []

        # ── Web search (fallback if no URLs/PDFs) ─────────────
        if web_search:
            logger.info("NarrativeAgent: executing live web search injection...")
            search_urls = self._live_web_search(query)
            urls.extend(search_urls)

        # ── URL scraping ──────────────────────────────────────
        for url in urls:
            logger.info(f"Omnivore: scraping {url}")
            text, imgs, labels = self._scrape_url(url)
            if text:
                all_docs.append(Document(page_content=text, metadata={"source": url}))
            all_images.extend(imgs)
            all_labels.extend(labels)

        # ── PDF parsing ───────────────────────────────────────
        for pdf_path in pdf_paths:
            logger.info(f"Omnivore: parsing {pdf_path}")
            text, imgs, labels = self._parse_pdf(pdf_path)
            if text:
                all_docs.append(Document(page_content=text, metadata={"source": pdf_path}))
            all_images.extend(imgs)
            all_labels.extend(labels)

        logger.info(
            f"Ingestion complete: {len(all_docs)} docs | "
            f"{len(all_images)} images"
        )
        return all_docs, all_images, all_labels

    # ── URL Scraper ───────────────────────────────────────────

    def _scrape_url(self, url: str) -> tuple[str, list[bytes], list[str]]:
        """
        Uses Jina Reader API to bypass bot-protection and extract clean markdown text.
        Downloads embedded images using regex.
        """
        import requests
        import urllib.parse
        import re

        try:
            logger.info(f"NarrativeAgent: using Jina Reader for {url}")
            jina_url = f"https://r.jina.ai/{url}"
            resp = requests.get(jina_url, timeout=25)
            resp.raise_for_status()
            text = resp.text

            images, labels = [], []
            
            # Extract image URLs from markdown: ![alt](url)
            img_matches = re.findall(r'!\[(.*?)\]\((.*?)\)', text)
            
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            }

            for alt, src in img_matches:
                if not src.startswith("http"):
                    src = urllib.parse.urljoin(url, src)
                try:
                    r = requests.get(src, headers=headers, timeout=8)
                    if self._is_meaningful_image(r.content):
                        images.append(r.content)
                        labels.append(alt if alt else f"Image from {url}")
                        if len(images) >= IMG_MAX_PER_SOURCE:
                            break
                except Exception:
                    continue

            return text, images, labels

        except Exception as e:
            logger.error(f"URL scrape failed for {url}: {e}")
            return "", [], []

    # ── PDF Parser ────────────────────────────────────────────

    def _parse_pdf(self, pdf_path: str) -> tuple[str, list[bytes], list[str]]:
        try:
            import fitz  # PyMuPDF
            from PIL import Image as PILImage

            doc  = fitz.open(pdf_path)
            text = ""
            images, labels = [], []

            for page_num, page in enumerate(doc):
                text += f"\n[Page {page_num + 1}]\n{page.get_text('text')}"

                for img_meta in page.get_images(full=True):
                    try:
                        xref     = img_meta[0]
                        base_img = doc.extract_image(xref)
                        w, h     = base_img["width"], base_img["height"]

                        # Size + aspect ratio filter
                        aspect = w / h if h > 0 else 0
                        if (w >= IMG_MIN_WIDTH and h >= IMG_MIN_HEIGHT and
                                IMG_MIN_ASPECT <= aspect <= IMG_MAX_ASPECT):
                            # Normalize to PNG for HUD consistency
                            pil = PILImage.open(io.BytesIO(base_img["image"]))
                            buf = io.BytesIO()
                            pil.save(buf, format="PNG")
                            images.append(buf.getvalue())
                            labels.append(f"Figure — page {page_num + 1}")

                        if len(images) >= IMG_MAX_PER_SOURCE:
                            break
                    except Exception:
                        continue

                if len(images) >= IMG_MAX_PER_SOURCE:
                    break

            doc.close()
            return text[:12000], images, labels

        except ImportError:
            logger.error("PyMuPDF not installed. Run: pip install pymupdf")
            return "", [], []
        except Exception as e:
            logger.error(f"PDF parse failed for {pdf_path}: {e}")
            return "", [], []

    # ── Hybrid Search (BM25 + FAISS + RRF) ───────────────────

    def _hybrid_search(self, query: str, documents: list) -> list:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_community.vectorstores import FAISS
        from langchain_community.retrievers import BM25Retriever

        splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=150)
        chunks   = splitter.split_documents(documents)

        if not chunks:
            return documents

        # Sparse — BM25
        bm25 = BM25Retriever.from_documents(chunks)
        bm25.k = 4
        sparse_docs = bm25.invoke(query)

        # Dense — FAISS
        vectorstore = FAISS.from_documents(chunks, self.embeddings)
        dense_docs  = vectorstore.similarity_search(query, k=4)

        # Reciprocal Rank Fusion
        scores = {}
        for doc_list in [sparse_docs, dense_docs]:
            for rank, doc in enumerate(doc_list):
                key = doc.page_content
                if key not in scores:
                    scores[key] = {"doc": doc, "score": 0.0}
                scores[key]["score"] += 1.0 / (rank + 60)

        ranked = sorted(scores.values(), key=lambda x: x["score"], reverse=True)
        logger.info(f"Hybrid search returned {len(ranked)} fused chunks")
        return [item["doc"] for item in ranked[:4]]

    # ── Documentary Synthesizer ───────────────────────────────

    def _synthesize_narrative(
        self, query: str, docs: list, image_labels: list[str]
    ) -> str:
        from langchain_core.messages import SystemMessage, HumanMessage

        context = "\n\n".join([d.page_content for d in docs])

        # Tell the LLM exactly which images exist so it can reference them
        image_inventory = ""
        if image_labels:
            image_inventory = "\n\nAVAILABLE VISUALS (reference these in your script):\n"
            for i, label in enumerate(image_labels):
                image_inventory += f"  [{i}] {label}\n"
            image_inventory += (
                "\nWhen shifting to visual evidence, insert a marker on its own line: "
                "[SHOW_IMAGE:0], [SHOW_IMAGE:1], etc."
            )

        system_prompt = (
            "You are JARVIS, an intelligence briefing system. "
            "Your output will be spoken aloud by a text-to-speech engine "
            "AND displayed on a visual HUD simultaneously. "
            "\n\nWrite a 3-part documentary script. "
            "Use ellipses (...) for dramatic pauses. "
            "Keep language clear and natural — no bullet points, no markdown, no asterisks. "
            "\n\nYOU MUST USE THESE EXACT SECTION TAGS:"
            "\n[SECTION: HOOK]"
            "\n(1-2 gripping sentences — the core conflict or breaking development)"
            "\n[SECTION: DEEP DIVE]"
            "\n(detailed breakdown of the data and facts from the retrieved context)"
            "\n[SECTION: SYNTHESIS]"
            "\n(the bigger picture — what this means and what comes next)"
            + image_inventory
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Query: {query}\n\nRetrieved Context:\n{context}"),
        ]

        response = self.llm.invoke(messages)
        return response.content

    # ── Cinematic Player ──────────────────────────────────────

    def _play_cinematic_story(
        self, script: str, images: list[bytes], labels: list[str]
    ):
        """
        Parses [SECTION:] tags, syncs HUD image transitions with
        speak_and_wait() so audio and visuals are always in lockstep.
        Section-level sync: each section gets one image.
        """
        # Split on section tags
        parts    = re.split(r'\[SECTION:\s*([^\]]+)\]', script)
        sections = []
        for i in range(1, len(parts), 2):
            title = parts[i].strip()
            text  = parts[i + 1].strip() if i + 1 < len(parts) else ""
            # Strip any inline [SHOW_IMAGE:N] markers from the spoken text
            clean_text = re.sub(r'\[SHOW_IMAGE:\d+\]', '', text).strip()
            # Clean asterisks and markdown Llama sometimes emits
            clean_text = re.sub(r'\*+', '', clean_text)
            sections.append({"title": title, "text": clean_text})

        if not sections:
            # Fallback: no section tags found — speak as one block
            mouth.speak_and_wait(re.sub(r'\[.*?\]', '', script).strip())
            return

        logger.info(f"Director: {len(sections)} sections found")
        
        full_clean_script = ""

        for idx, section in enumerate(sections):
            logger.info(f"Playing section: {section['title']}")

            # ── Push image to HUD ──────────────────────────────
            if images:
                img_idx    = min(idx, len(images) - 1)
                caption    = labels[img_idx] if img_idx < len(labels) else section["title"]
                hud.update_image_bytes(images[img_idx], caption=caption)
                hud.update_status(f"Section {idx + 1}/{len(sections)}: {section['title']}")

            # ── Speak and broadcast text ──────────────────────────────
            if section["text"]:
                full_clean_script += section["text"] + "\n\n"
                
                # Split by sentence boundaries, keeping punctuation
                sentences = re.split(r'(?<=[.!?])\s+', section["text"].strip())
                
                for sentence in sentences:
                    if not sentence.strip():
                        continue
                        
                    # Broadcast the clean sentence to the Web UI right before speaking
                    try:
                        from core.events import event_bus
                        event_bus.emit("broadcast", {
                            "type": "result",
                            "agent": self.name,
                            "text": sentence.strip(),
                            "confidence": 0.9
                        })
                    except Exception as e:
                        logger.error(f"Failed to broadcast text: {e}")
                        
                    mouth.speak_and_wait(sentence.strip())
                
        return full_clean_script.strip()

    # ── Mock web search ───────────────────────────────────────

    def _live_web_search(self, query: str) -> list[str]:
        """
        Uses duckduckgo-search to find the top 3 live internet URLs for the query.
        """
        try:
            from ddgs import DDGS
            logger.info(f"NarrativeAgent: searching live web for '{query}'...")
            results = DDGS().text(query, max_results=3)
            urls = [r["href"] for r in results if "href" in r]
            logger.info(f"NarrativeAgent: found {len(urls)} URLs from search")
            return urls
        except ImportError:
            logger.error("NarrativeAgent: duckduckgo-search not installed!")
            return []
        except Exception as e:
            logger.error(f"NarrativeAgent: web search failed: {e}")
            return []

    # ── Image filter ──────────────────────────────────────────

    def _is_meaningful_image(self, img_bytes: bytes) -> bool:
        try:
            from PIL import Image as PILImage
            img    = PILImage.open(io.BytesIO(img_bytes))
            w, h   = img.size
            aspect = w / h if h > 0 else 0
            return (
                w >= IMG_MIN_WIDTH and
                h >= IMG_MIN_HEIGHT and
                IMG_MIN_ASPECT <= aspect <= IMG_MAX_ASPECT
            )
        except Exception:
            return False
