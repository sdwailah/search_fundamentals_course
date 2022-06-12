# From https://github.com/dshvadskiy/search_with_machine_learning_course/blob/main/index_products.py
import requests
from lxml import etree

import click
import glob
from opensearchpy import OpenSearch
from opensearchpy.helpers import bulk
import logging
import time
import json

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
logging.basicConfig(format='%(levelname)s:%(message)s')

# NOTE: this is not a complete list of fields.  If you wish to add more, put in the appropriate XPath expression.
# TODO: is there a way to do this using XPath/XSL Functions so that we don't have to maintain a big list?
mappings = [
    "sku/text()", "sku", # SKU is the unique ID, productIds can have multiple skus
    "upc/text()", "upc",
    "productId/text()", "productId",
    "name/text()", "name",
    "type/text()", "type",
    "regularPrice/text()", "regularPrice",
    "salePrice/text()", "salePrice",
    "onSale/text()", "onSale",
    "salesRankShortTerm/text()", "salesRankShortTerm",
    "salesRankMediumTerm/text()", "salesRankMediumTerm",
    "salesRankLongTerm/text()", "salesRankLongTerm",
    "bestSellingRank/text()", "bestSellingRank",
    "url/text()", "url",
    "categoryPath/*/name/text()", "categoryPath",  # Note the match all here to get the subfields
    "categoryPath/*/id/text()", "categoryPathIds",  # Note the match all here to get the subfields
    "categoryPath/category[last()]/id/text()", "categoryLeaf",
    "count(categoryPath/*/name)", "categoryPathCount",
    "customerReviewCount/text()", "customerReviewCount",
    "customerReviewAverage/text()", "customerReviewAverage",
    "inStoreAvailability/text()", "inStoreAvailability",
    "onlineAvailability/text()", "onlineAvailability",
    "releaseDate/text()", "releaseDate",
    "shortDescription/text()", "shortDescription",
    "class/text()", "class",
    "classId/text()", "classId",
    "department/text()", "department",
    "departmentId/text()", "departmentId",
    "bestBuyItemId/text()", "bestBuyItemId",
    "description/text()", "description",
    "manufacturer/text()", "manufacturer",
    "modelNumber/text()", "modelNumber",
    "image/text()", "image",
    "longDescription/text()", "longDescription",
    "longDescriptionHtml/text()", "longDescriptionHtml",
    "features/*/text()", "features"  # Note the match all here to get the subfields
]


def get_opensearch():
    host = 'localhost'
    port = 9200
    auth = ('admin', 'admin')

    #### Step 2.a: Create a connection to OpenSearch
    #client = None
    client = OpenSearch(
        hosts = [{'host': host, 'port': port}],
        http_compress = True,
        http_auth = auth,
        use_ssl=True,
        verify_certs=False,
        ssl_assert_hostname=False,
        ssl_show_warn=False,
    )
    print(client.cat.health())
    print(client.cat.indices())
    return client

def getBoolenValue(boolenStr):
    boolenValue = None
    if(len(boolenStr) > 0):
        if(boolenStr == "ture" or boolenStr == "Ture"):
            boolenValue = True
        else:
            boolenValue = False
    return boolenValue

def getIntValue(intStr):
    intValue = ""
    if(len(intStr) > 0):
        if(intStr[0]):
            intValue = int(intStr[0])
    return intValue

def getFloatValue(floatStr):
    floatValue = ""
    if(len(floatStr) > 0):
        if(floatStr[0]):
            floatValue = float(floatStr[0])
    return floatValue

def getStringValue(stringArray):
    stringValue = None
    if(len(stringArray) > 0):
        stringValue = stringArray[0]
    return stringValue

def getDataValue(dateStr):
    dateValue = None
    if(len(dateStr) > 0):
        dateValue = dateStr[0]
    return dateValue

def getOpenSearchDoc(OriginalDoc):

    fixDoc={
        "id": OriginalDoc["productId"][0] + OriginalDoc["sku"][0],
        '_index': "bbuy_products",
        "sku": getStringValue(OriginalDoc["sku"]),
        "upc": getStringValue(OriginalDoc["upc"]),
        "productId": OriginalDoc["productId"][0],
        "name": getStringValue(OriginalDoc["name"]),
        "type" : getStringValue(OriginalDoc["type"]),
        "regularPrice": getFloatValue(OriginalDoc["regularPrice"]),
        "salePrice": getFloatValue( OriginalDoc["salePrice"]) ,
        "onSale": getBoolenValue(OriginalDoc["onSale"]) ,
        "salesRankShortTerm": getIntValue(OriginalDoc["salesRankShortTerm"]),
        "salesRankMediumTerm": getIntValue(OriginalDoc["salesRankMediumTerm"]),
        "salesRankLongTerm": getIntValue(OriginalDoc["salesRankLongTerm"]),
        "bestSellingRank": getIntValue(OriginalDoc["bestSellingRank"]),
        "url": getStringValue(OriginalDoc["url"]),
        "categoryPath":OriginalDoc["categoryPath"],
        "categoryPathIds": OriginalDoc["categoryPathIds"],
        "categoryLeaf": OriginalDoc["categoryLeaf"],
        "categoryPathCount": OriginalDoc["categoryPathCount"],
        "customerReviewAverage": getFloatValue(OriginalDoc["customerReviewAverage"]),
        "inStoreAvailability": getBoolenValue(OriginalDoc["inStoreAvailability"]),
        "onlineAvailability": getBoolenValue(OriginalDoc["onlineAvailability"]),
        "releaseDate": getDataValue(OriginalDoc["releaseDate"]),
        "shortDescription": getStringValue(OriginalDoc["shortDescription"]),
        "class": getStringValue(OriginalDoc["class"]),
        "classId": getIntValue(OriginalDoc["classId"]),
        "department": getStringValue(OriginalDoc["department"]),
        "departmentId": getIntValue(OriginalDoc["departmentId"]),
        "bestBuyItemId": getIntValue(OriginalDoc["bestBuyItemId"]),
        "description": getStringValue(OriginalDoc["description"]),
        "manufacturer": getStringValue(OriginalDoc["manufacturer"]),
        "modelNumber": getStringValue(OriginalDoc["modelNumber"]),
        "image": OriginalDoc["image"],
        "longDescription": getStringValue(OriginalDoc["longDescription"]),
        "longDescriptionHtml": getStringValue(OriginalDoc["longDescriptionHtml"]),
        "features": OriginalDoc["features"]
    }
    return fixDoc


@click.command()
@click.option('--source_dir', '-s', help='XML files source directory')
@click.option('--index_name', '-i', default="bbuy_products", help="The name of the index to write to")
def main(source_dir: str, index_name: str):
    print("========================================")

    client = get_opensearch()
    # To test on a smaller set of documents, change this glob to be more restrictive than *.xml
    files = glob.glob(source_dir + "/*.xml")


    numberOfIndexedFile = 0
    docs_indexed = 0
    tic = time.perf_counter()
    for file in files:
        numberOfIndexedFile += 1
        logger.info(f'Processing file : {file}')
        tree = etree.parse(file)
        root = tree.getroot()
        children = root.findall("./product")
        docs = []
        for child in children:
            doc = {}
            for idx in range(0, len(mappings), 2):
                xpath_expr = mappings[idx]
                key = mappings[idx + 1]
                doc[key] = child.xpath(xpath_expr)


            if not 'productId' in doc or len(doc['productId']) == 0:
                continue

            #### Step 2.b: Create a valid OpenSearch Doc and bulk index 2000 docs at a time

            getOpenSearchDoc(doc)

            #print(doc)
            the_doc = getOpenSearchDoc(doc)
            docs_indexed += 1
            logger.info(f'Doc Id :  + {the_doc["id"]}')


            docs.append(the_doc)
            if(len(docs) > 2000 ):
                bulk(client, docs)
                docs = []

    logger.info(f'the total number of indexed file : {numberOfIndexedFile}')
    logger.info(f'the total number of indexed document : {docs_indexed}')
    toc = time.perf_counter()
    logger.info(f'Done. Total docs: {docs_indexed}.  Total time: {((toc - tic) / 60):0.3f} mins.')


if __name__ == "__main__":
    main()
