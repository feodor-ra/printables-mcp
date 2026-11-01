"""Structured tool results and their construction from raw API payloads."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .markdown import html_to_markdown
from .refs import author_url, media_url, model_url

FileKind = Literal["stl", "gcode", "sla", "other", "pack"]

_FILE_GROUPS: tuple[tuple[str, FileKind], ...] = (
    ("stls", "stl"),
    ("gcodes", "gcode"),
    ("slas", "sla"),
    ("otherFiles", "other"),
    ("downloadPacks", "pack"),
)


def _number(value: str | float | None) -> float | None:
    return None if value is None else float(value)


def _minutes(hours: str | float | None) -> int | None:
    return None if hours is None else round(float(hours) * 60)


def _text(value: str | None) -> str | None:
    return (value or "").strip() or None


class Author(BaseModel):
    """Who published a model."""

    id: str
    handle: str
    name: str | None = Field(description="Public display name")
    url: str


def _author_fields(user: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": user["id"],
        "handle": user["handle"],
        "name": user.get("publicUsername"),
        "url": author_url(user["handle"]),
    }


class Category(BaseModel):
    """A model category; ``path`` lists its ancestors from the root."""

    id: str
    name: str
    path: str = Field(description='Full path, e.g. "3D Printers / Test Models"')

    @classmethod
    def from_api(cls, category: dict[str, Any]) -> Category:
        """Build from a ``CategoryType`` payload (``path`` is optional).

        Returns:
            The category.
        """
        path = category.get("path") or [category]
        return cls(id=category["id"], name=category["name"], path=" / ".join(node["name"] for node in path))


class License(BaseModel):
    """A content license a model can be published under."""

    id: str
    name: str
    abbreviation: str | None

    @classmethod
    def from_api(cls, license_: dict[str, Any]) -> License:
        """Build from a ``LicenseType`` payload.

        Returns:
            The license.
        """
        return cls(id=license_["id"], name=license_["name"].strip(), abbreviation=license_.get("abbreviation"))


class _ModelBase(BaseModel):
    id: str
    name: str
    url: str
    author: Author | None
    category: Category | None
    published: str | None = Field(description="Publication timestamp, ISO 8601")
    rating: float | None = Field(description="Average rating, 0-5")
    ratings: int | None = Field(description="Number of ratings")
    likes: int | None
    downloads: int | None
    makes: int | None = Field(description="Number of user-posted prints of the model")
    is_free: bool = Field(description="Free to download without purchase or a club membership")
    price: float | None = Field(description="Purchase price in USD for paid models")
    club_only: bool = Field(description="Available to Printables Club members only")
    nsfw: bool

    @staticmethod
    def _common(model: dict[str, Any]) -> dict[str, Any]:
        price = _number(model.get("price"))
        club_only = bool(model.get("premium"))
        user = model.get("user")
        category = model.get("category")
        rating = _number(model.get("ratingAvg"))
        return {
            "id": model["id"],
            "name": model["name"],
            "url": model_url(model["id"], model.get("slug")),
            "author": Author(**_author_fields(user)) if user else None,
            "category": Category.from_api(category) if category else None,
            "published": model.get("datePublished"),
            "rating": None if rating is None else round(rating, 2),
            "ratings": model.get("ratingCount"),
            "likes": model.get("likesCount"),
            "downloads": model.get("downloadCount"),
            "makes": model.get("makesCount"),
            "is_free": price is None and not club_only,
            "price": price,
            "club_only": club_only,
            "nsfw": bool(model.get("nsfw")),
        }


class ModelSummary(_ModelBase):
    """A model as listed in search results and author listings."""

    image_url: str | None

    @classmethod
    def from_api(cls, model: dict[str, Any]) -> ModelSummary:
        """Build from a ``PrintType`` payload selected with the ``ModelSummary`` fragment.

        Returns:
            The summary.
        """
        return cls(**cls._common(model), image_url=media_url((model.get("image") or {}).get("filePath")))


class RemixSource(BaseModel):
    """What a model is a remix of: another Printables model or an external page."""

    model_id: str | None
    name: str | None
    url: str | None

    @classmethod
    def from_api(cls, parent: dict[str, Any]) -> RemixSource:
        """Build from a ``PrintRemixType`` payload.

        Returns:
            The remix source.
        """
        parent_id = parent.get("parentPrintId")
        return cls(
            model_id=parent_id,
            name=parent.get("parentPrintName"),
            url=model_url(parent_id, None) if parent_id else parent.get("url"),
        )


class ModelDetails(_ModelBase):
    """Everything about one model except its files."""

    summary: str | None
    description: str = Field(description="Full description as Markdown")
    authorship: str | None = Field(description='"original", "remix" or "reupload"')
    first_published: str | None
    views: int | None
    comments: int | None
    license: License | None
    tags: list[str]
    materials: list[str]
    printer: str | None = Field(description="Printer the author used")
    print_time_minutes: int | None
    weight_grams: float | None = Field(description="Filament weight")
    multi_material: bool
    images: list[str]
    pdf_url: str | None
    remix_of: list[RemixSource]

    @classmethod
    def from_api(cls, model: dict[str, Any]) -> ModelDetails:
        """Build from a ``PrintType`` payload selected by ``GET_MODEL``.

        Returns:
            The model details.
        """
        license_ = model.get("license")
        return cls(
            **cls._common(model),
            summary=_text(model.get("summary")),
            description=html_to_markdown(model.get("description")),
            authorship=model.get("authorship"),
            first_published=model.get("firstPublish"),
            views=model.get("displayCount"),
            comments=model.get("commentCount"),
            license=License.from_api(license_) if license_ else None,
            tags=[tag["name"] for tag in model.get("tags") or []],
            materials=[material["name"] for material in model.get("materials") or []],
            printer=(model.get("printer") or {}).get("name"),
            print_time_minutes=_minutes(model.get("printDuration")),
            weight_grams=_number(model.get("weight")),
            multi_material=bool(model.get("mmu")),
            images=[
                url for image in model.get("images") or [] if (url := media_url(image.get("filePath"))) is not None
            ],
            pdf_url=media_url(model.get("pdfFilePath")),
            remix_of=[RemixSource.from_api(parent) for parent in model.get("remixParents") or []],
        )


class ModelFile(BaseModel):
    """A downloadable file of a model. Slicing fields are filled for G-code and SLA files only."""

    id: str
    kind: FileKind = Field(
        description="stl: model files (STL, 3MF, STEP...); gcode: sliced G-code; sla: resin print files; "
        "other: anything else; pack: ZIP archive of a whole group"
    )
    name: str
    size_bytes: int | None
    folder: str | None
    note: str | None
    preview_url: str | None
    printer: str | None = None
    material: str | None = None
    print_time_minutes: int | None = None
    layer_height_mm: float | None = None
    nozzle_diameter_mm: float | None = None
    weight_grams: float | None = None

    @classmethod
    def from_api(cls, item: dict[str, Any], kind: FileKind) -> ModelFile:
        """Build from one file entry of any group in ``MODEL_FILES``.

        Returns:
            The file.
        """
        name = item.get("name") or ""
        if kind == "pack":
            group = str(item.get("fileType") or "files").lower().replace("_", " ")
            name = name or f"All {group} (ZIP)"
        return cls(
            id=item["id"],
            kind=kind,
            name=name,
            size_bytes=item.get("fileSize"),
            folder=_text(item.get("folder")),
            note=_text(item.get("note")),
            preview_url=media_url(item.get("filePreviewPath")),
            printer=(item.get("printer") or {}).get("name"),
            material=(item.get("material") or {}).get("name"),
            print_time_minutes=_minutes(item.get("printDuration")),
            layer_height_mm=_number(item.get("layerHeight")),
            nozzle_diameter_mm=_number(item.get("nozzleDiameter")),
            weight_grams=_number(item.get("weight")),
        )


class ModelFiles(BaseModel):
    """All downloadable files of a model."""

    model_id: str
    model_url: str
    files: list[ModelFile]

    @classmethod
    def from_api(cls, model: dict[str, Any]) -> ModelFiles:
        """Build from the payload of ``MODEL_FILES``.

        Returns:
            The file listing.
        """
        files = [ModelFile.from_api(item, kind) for group, kind in _FILE_GROUPS for item in model.get(group) or []]
        return cls(model_id=model["id"], model_url=model_url(model["id"], model.get("slug")), files=files)


class DownloadLink(BaseModel):
    """A direct download link for one file, or the reason it could not be issued."""

    file_id: str
    kind: FileKind | None
    name: str | None
    url: str | None
    expires_in_seconds: int | None
    error: str | None = Field(
        default=None, description='Why no link was issued, e.g. "cannot_download_premium_file_as_anonymous_user"'
    )


class DownloadLinks(BaseModel):
    """Download links for the requested files of a model."""

    model_id: str
    links: list[DownloadLink]


class SearchResults(BaseModel):
    """One page of search results."""

    total: int = Field(description="Total number of matches (the API caps it at 10000)")
    offset: int
    items: list[ModelSummary]


class Categories(BaseModel):
    """All model categories."""

    categories: list[Category]


class Licenses(BaseModel):
    """All licenses models can be published under."""

    licenses: list[License]


class AuthorProfile(Author):
    """An author's public profile."""

    followers: int | None
    bio: str | None

    @classmethod
    def from_api(cls, user: dict[str, Any]) -> AuthorProfile:
        """Build from the payload of ``GET_AUTHOR``.

        Returns:
            The profile.
        """
        return cls(
            **_author_fields(user),
            followers=user.get("followersCount"),
            bio=_text(user.get("bio")),
        )


class AuthorModels(BaseModel):
    """One page of an author's models."""

    items: list[ModelSummary]
    next_cursor: str | None = Field(description="Pass as `cursor` to fetch the next page; null on the last page")
