import os
from datetime import datetime, timezone
from typing import List, Optional

import instructor
import markdown
import requests
from asgiref.sync import async_to_sync
from bs4 import BeautifulSoup
from celery import shared_task
from celery.result import AsyncResult
from llama_index.core import ChatPromptTemplate
from llama_index.core.llms import ChatMessage, MessageRole
from llama_index.core.workflow import (
    Context,
    Event,
    StartEvent,
    StopEvent,
    Workflow,
    step,
)
from llama_index.llms.azure_openai import AzureOpenAI as LlamaAzureOpenAI
from loguru import logger
from openai import AsyncAzureOpenAI
from trafilatura import extract, fetch_url

from producthunt_ideator.settings import settings
from producthunt_ideator.web.api.ideator.schema import Analysis, TaskOut


class Product:
    """
    A class representing a product with various attributes and methods to generate descriptions and fetch image URLs.

        id (str): The unique identifier of the product.
        name (str): The name of the product.
        tagline (str): The tagline of the product.
        description (str): A brief description of the product.
        votes_count (int): The number of votes the product has received.
        created_at (str): The creation date of the product.
        website (str): The website URL of the product.
        url (str): The URL of the product's page on Product Hunt.
        featured (bool): Indicates if the product is featured.
        topics (list): A list of topics associated with the product.
        long_description (str): A detailed description of the product generated by an AI model.
        og_image_url (str): The URL of the product's Open Graph image.
    Methods:
        __init__(self, id: str, name: str, tagline: str, description: str, votesCount: int, createdAt: str,
                website: str, url: str, featuredAt: Optional[str] = None, topics: dict = {}, **kwargs) -> None:
            Initializes a Product instance with the provided attributes.
        _extract_landing_page_text(self) -> str:
            Extracts and returns the text content from the product's landing page.
        async generate_description(self, llm: AzureOpenAI) -> None:
            Asynchronously generates a concise and insightful description of the product using Azure OpenAI.
        fetch_og_image_url(self) -> None:
            Fetches the Open Graph image URL of the product from its Product Hunt webpage.
        __str__(self) -> str:
            Returns a string representation of the product with its name, tagline, description, long description, and website.
    """  # noqa: E501

    def __init__(
        self,
        id: str,
        name: str,
        tagline: str,
        description: str,
        votesCount: int,
        createdAt: str,
        website: str,
        url: str,
        featuredAt: Optional[str] = None,
        topics: dict = {},
        **kwargs,
    ) -> None:
        self.name = name
        self.tagline = tagline
        self.description = description
        self.votes_count = votesCount
        self.created_at = createdAt
        self.featured = bool(featuredAt)
        self.website = website
        self.url = url
        self.topics = [topic["node"]["name"] for topic in topics["edges"]]
        self.long_description = ""
        self.og_image_url = ""

    def _extract_landing_page_text(self) -> str:
        downloaded = fetch_url(self.website)
        document = extract(downloaded)
        return document if document else ""

    async def generate_description(self, llm: LlamaAzureOpenAI) -> None:
        """Asynchronously generates a concise and insightful description of a product using Azure OpenAI.

        This method extracts the landing page text and uses it along with the product's name, tagline,
        and description to create a summary. The summary highlights the core functionality and value
        proposition of the product, ensuring it is clear, engaging, and no longer than 50 words.
        Args:
            llm (AzureOpenAI): An instance of AzureOpenAI used to generate the description.
        Returns:
            None: The generated description is stored in the `long_description` attribute of the instance.
        """  # noqa: E501
        landing_page_text = self._extract_landing_page_text()
        system_content = """
        You are a summarization assistant tasked with creating concise, insightful
        descriptions of products based on the provided information.
        Use the name, tagline, description, and raw landing page text to craft a clear,
        engaging summary. The summary should:

        Highlight the core functionality and value proposition of the product.
        Avoid repeating any one source verbatim.
        Be no longer than 50 words.
        Your summaries will serve as input for another assistant tasked with reimagining
        these products fornew industries,demographics, or trends.
        Focus on clarity, potential appeal, and unique aspects.
        Do not introduce speculative details or solutions.
        """
        user_content = f"""
        Name: {self.name}
        Tagline: {self.tagline}
        Description: {self.description}
        Landing Page Text: {landing_page_text}
        """
        system_msg = ChatMessage(content=system_content, role=MessageRole.SYSTEM)
        user_msg = ChatMessage(content=user_content, role=MessageRole.USER)
        chat_template = ChatPromptTemplate(message_templates=[system_msg, user_msg])
        messages = chat_template.format_messages()
        response = await llm.achat(messages)
        self.long_description = response.message.content

    def fetch_og_image_url(self) -> None:
        """
        Fetches the image URL of the product from the producthunt webpage.

        This method sends a GET request to the URL stored in the `self.url` attribute,
        parses the HTML content of the response, and extracts the OG image URL from
        the meta tag with the property "og:image". If the OG image URL is found, it
        is stored in the `self.og_image_url` attribute.

        Raises:
            requests.exceptions.RequestException: If there is an issue
            with the GET request.
            requests.exceptions.Timeout: If the request times out.

        Attributes:
            self.url (str): The URL of the webpage to fetch the OG image from.
            self.og_image_url (str): The extracted OG image URL, if found.
        """
        response = requests.get(
            self.url,
            timeout=20,
        )  # Specify a timeout of 10 seconds
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            og_image = soup.find("meta", property="og:image")
            if og_image:
                self.og_image_url = og_image["content"]

    def to_markdown(self) -> str:
        og_image_markdown = f"![{self.name}]({self.og_image_url})"
        return (
            f"## [{self.name}]({self.url})\n"
            f"**Tagline**: {self.tagline}\n"
            f"**Description**: {self.long_description}\n"
            f"[View on Product Hunt]({self.url})\n\n"
            f"{og_image_markdown}\n\n"
            f"**Votes**: 🔺{self.votes_count}\n"
            f"**Featured**: {self.featured}\n"
            f"**Created**: {self.created_at}\n\n"
        )

    def __str__(self) -> str:
        return f"""
        Name: {self.name}
        Tagline: {self.tagline}
        Description: {self.description}
        Long Description: {self.long_description}
        Website: {self.website}
        """


class ProductEvent(Event):
    product: Product


class ReimagineEvent(Event):
    product: Product


class FinalResultEvent(Event):
    product: Product
    proposal: Analysis


class IdeatorWorkflow(Workflow):
    llm = LlamaAzureOpenAI(
        model=settings.gpt_model,
        deployment_name=settings.gpt_model,
        api_key=settings.openai_api_key,
        azure_endpoint=settings.azure_openai_endpoint,
        api_version="2024-08-01-preview",
    )
    client = instructor.from_openai(
        AsyncAzureOpenAI(
            azure_deployment=settings.gpt_model,
            api_key=settings.openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version="2024-08-01-preview",
        ),
    )

    def __init__(
        self,
        timeout: Optional[float] = 10.0,
        verbose: bool = False,
        num_concurrent_runs: Optional[int] = None,
    ) -> None:
        super().__init__(timeout, verbose, num_concurrent_runs=num_concurrent_runs)
        self.token = self._get_producthunt_token()

    def _get_producthunt_token(self) -> str:
        url = "https://api.producthunt.com/v2/oauth/token"
        payload = {
            "client_id": settings.producthunt_client_id,
            "client_secret": settings.producthunt_client_secret,
            "grant_type": "client_credentials",
        }

        headers = {
            "Content-Type": "application/json",
        }

        response = requests.post(url, json=payload, headers=headers, timeout=20)

        if response.status_code != 200:
            raise Exception(
                f"Failed to obtain access token: {response.status_code}, {response.text}",
            )

        return response.json().get("access_token")

    @step
    async def _fetch_product_hunt_data(  # type: ignore
        self,
        ctx: Context,
        ev: StartEvent,
    ) -> ProductEvent:  # type: ignore
        date_str = ev.date
        url = "https://api.producthunt.com/v2/api/graphql"
        headers = {"Authorization": f"Bearer {self.token}"}

        base_query = """
        {
        posts(order: VOTES, postedAfter: "%sT00:00:00Z", postedBefore: "%sT23:59:59Z", after: "%s") {
            nodes {
            id
            name
            tagline
            description
            votesCount
            createdAt
            featuredAt
            website
            url
            topics {
                edges {
                node {
                    name
                }
                }
            }
            }
            pageInfo {
            hasNextPage
            endCursor
            }
        }
        }
        """  # noqa: E501

        all_posts = []
        has_next_page = True
        cursor = ""

        while has_next_page and len(all_posts) < settings.post_limit:
            query = base_query % (date_str, date_str, cursor)
            response = requests.post(
                url,
                headers=headers,
                json={"query": query},
                timeout=20,
            )

            if response.status_code != 200:
                raise Exception(
                    f"""Failed to fetch data from Product Hunt:
                    {response.status_code}, {response.text}
                    """,
                )

            data = response.json()["data"]["posts"]
            posts = data["nodes"]
            all_posts.extend(posts)

            has_next_page = data["pageInfo"]["hasNextPage"]
            cursor = data["pageInfo"]["endCursor"]

        products = [
            Product(**post)
            for post in sorted(all_posts, key=lambda x: x["votesCount"], reverse=True)[
                : settings.post_limit
            ]
        ]
        for product in products:
            ctx.send_event(ProductEvent(product=product))

    @step(num_workers=settings.post_limit)
    async def _process_product(self, ctx: Context, ev: ProductEvent) -> ReimagineEvent:  # type: ignore
        product = ev.product
        logger.info(f"Processing product: {product.name}")
        await product.generate_description(self.llm)
        product.fetch_og_image_url()
        ctx.send_event(ReimagineEvent(product=product))

    @step(num_workers=settings.post_limit)
    async def _reimagine_product(  # type: ignore
        self,
        ctx: Context,
        ev: ReimagineEvent,
    ) -> FinalResultEvent:  # type: ignore
        logger.info(f"Reimagining product: {ev.product.name}")
        product = ev.product
        system_content = """
        You are an innovation assistant specializing in reimagining
        existing product ideas for B2B applications.
        Based on the provided product summary, your task is to:

        Identify Gaps or Potential: Analyze areas where the product could improve,
        expand its functionality, or address unmet needs for businesses.
        Adapt the Idea: Propose innovative ways to apply the concept to new industries,
        business demographics, geographies, or B2B business models.
        Integrate Emerging Trends: Suggest ways to incorporate cutting-edge technologies
        or societal trends (e.g., generative AI, sustainability, blockchain)
        while maintaining relevance to B2B markets.
        Focus on creating solutions that enhance efficiency, profitability, or
        operational capacity for businesses. Think of examples like Slack,
        which adapted instant messaging to improve workplace communication, or Shopify,
        which transformed e-commerce infrastructure for merchants.
        Similarly, your ideas should aim to offer measurable value to organizations.

        Your output should include:

        A brief analysis of the product's current strengths and weaknesses.
        Three distinct B2B-focused reimagination proposals, prioritizing practicality,
        originality, and market alignment.
        Avoid generic or vague suggestions; prioritize detail, clarity,
        and creativity while tailoring all solutions to B2B applications.
        """
        user_content = f"""
        Product Name: {product.name}
        Product Tagline: {product.tagline}
        Product Description: {product.description} {product.long_description}
        """
        system_msg = ChatMessage(content=system_content, role=MessageRole.SYSTEM)
        user_msg = ChatMessage(content=user_content, role=MessageRole.USER)
        chat_template = ChatPromptTemplate(message_templates=[system_msg, user_msg])
        messages = chat_template.format_messages()

        if settings.instructor:
            dict_messages = [message.dict() for message in messages]
            proposal = await self.client.chat.completions.create(
                model=settings.gpt_model,
                response_model=Analysis,
                messages=dict_messages,  # type: ignore
            )  # type: ignore
        else:
            sllm = self.llm.as_structured_llm(output_cls=Analysis)
            response = await sllm.achat(messages)
            proposal = response.raw

        ctx.send_event(
            FinalResultEvent(product=product, proposal=proposal),
        )

    @step
    async def _collect_results(self, ctx: Context, ev: FinalResultEvent) -> StopEvent:
        # wait until we receive 3 events
        result = ctx.collect_events(ev, [FinalResultEvent] * settings.post_limit)
        if result is None:
            return None

        return StopEvent(result=result)


def generate_markdown(events: List[FinalResultEvent], date: str) -> None:
    markdown_content = f"# ProductHunt Top {settings.post_limit} | {date}\n\n"
    for event in events:
        markdown_content += event.product.to_markdown()
        markdown_content += event.proposal.to_markdown()
        markdown_content += "---\n\n"

    os.makedirs("data", exist_ok=True)

    file_name = f"data/producthunt-daily-{date}.md"

    with open(file_name, "w", encoding="utf-8") as file:
        file.write(markdown_content)
    logger.info(f"Created {file_name} file with today's Product Hunt data.")


@shared_task
def run_workflow(date: str) -> None:
    w = IdeatorWorkflow(timeout=None, verbose=False)
    events = async_to_sync(w.run)(date=date)
    generate_markdown(events, date)


@shared_task
def publish_to_wordpress() -> None:
    today = datetime.now(timezone.utc)
    date_today = today.strftime("%Y-%m-%d")

    file_name = f"data/producthunt-daily-{date_today}.md"
    try:
        with open(file_name, "r", encoding="utf-8") as file:
            content = file.read()
    except FileNotFoundError:
        logger.error(f"Error: File not found: {file_name}")
        return

    lines = content.splitlines()
    if lines and lines[0].startswith("#"):
        lines = lines[1:]
    content_without_title = "\n".join(lines)

    html_content = markdown.markdown(content_without_title)

    title = content.splitlines()[0].strip("#").strip()

    slug = os.path.basename(file_name).replace(".md", "")

    post_data = {
        "title": title,
        "content": html_content,
        "status": "publish",
        "slug": slug,
        "categories": [337],
    }

    headers = {"Content-Type": "application/json"}

    api_url = f"{settings.wordpress_url}/wp-json/wp/v2/posts"

    response = requests.post(
        api_url,
        json=post_data,
        headers=headers,
        auth=(settings.wordpress_user, settings.wordpress_password),
        allow_redirects=False,
        timeout=30,
    )

    if response.status_code == 201:
        logger.info("Post published successfully.")
    else:
        logger.error(f"Failed to publish post: {response.status_code}, {response.text}")
        # saving response to a file for debugging
        with open(f"data/error_{slug}.json", "w", encoding="utf-8") as file:
            file.write(response.text)


def _to_task_out(r: AsyncResult) -> TaskOut:
    return TaskOut(id=r.task_id, status=r.status)
