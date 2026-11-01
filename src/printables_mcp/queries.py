"""GraphQL documents sent to the Printables API."""

_MODEL_SUMMARY = """
fragment ModelSummary on PrintType {
  id name slug datePublished
  ratingAvg ratingCount likesCount downloadCount makesCount
  premium price nsfw
  user { id handle publicUsername }
  image { filePath }
  category { id name path { id name } }
}
"""

SEARCH_MODELS = (
    """
query SearchModels(
  $query: String!, $limit: Int, $offset: Int, $ordering: SearchChoicesEnum, $categoryId: ID,
  $paid: PaidEnum, $licenses: [ID], $publishedDateLimitDays: Int, $hasMake: Boolean
) {
  result: searchPrints2(
    query: $query, printType: print, limit: $limit, offset: $offset, ordering: $ordering,
    categoryId: $categoryId, paid: $paid, licenses: $licenses,
    publishedDateLimitDays: $publishedDateLimitDays, hasMake: $hasMake
  ) {
    totalCount
    items { ...ModelSummary }
  }
}
"""
    + _MODEL_SUMMARY
)

GET_MODEL = """
query GetModel($id: ID!) {
  model: print(id: $id) {
    id name slug summary description authorship
    datePublished firstPublish
    ratingAvg ratingCount likesCount downloadCount displayCount makesCount commentCount
    premium price nsfw mmu
    printDuration weight
    user { id handle publicUsername }
    category { id name path { id name } }
    license { id name abbreviation }
    tags { name }
    materials { name }
    printer { name }
    images { filePath }
    pdfFilePath
    remixParents { parentPrintId parentPrintName url }
  }
}
"""

MODEL_FILES = """
query ModelFiles($id: ID!) {
  model: print(id: $id) {
    id slug
    stls { id name fileSize folder note filePreviewPath }
    gcodes {
      id name fileSize folder note filePreviewPath
      printDuration layerHeight nozzleDiameter weight
      printer { name }
      material { name }
    }
    slas { id name fileSize folder note filePreviewPath printDuration layerHeight printer { name } }
    otherFiles { id name fileSize folder note filePreviewPath }
    downloadPacks { id name fileSize fileType }
  }
}
"""

GET_DOWNLOAD_LINK = """
mutation GetDownloadLink($id: ID!, $modelId: ID!, $fileType: DownloadFileTypeEnum!) {
  result: getDownloadLink(id: $id, printId: $modelId, fileType: $fileType, source: model_detail) {
    ok
    errors { field messages }
    output { link ttl }
  }
}
"""

LIST_CATEGORIES = """
query ListCategories {
  categories { id name path { id name } }
}
"""

LIST_LICENSES = """
query ListLicenses {
  licenses { id name abbreviation }
}
"""

GET_AUTHOR = """
query GetAuthor($id: ID!) {
  user(id: $id) { id handle publicUsername followersCount bio }
}
"""

AUTHOR_MODELS = (
    """
query AuthorModels($userId: ID!, $limit: Int, $cursor: String, $ordering: String) {
  result: userModels(userId: $userId, limit: $limit, cursor: $cursor, ordering: $ordering) {
    cursor
    items { ...ModelSummary }
  }
}
"""
    + _MODEL_SUMMARY
)
