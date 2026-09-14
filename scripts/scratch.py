import sys
import traceback
from pathlib import Path

sys.path.append(str(Path(__file__).parent.resolve()))

from xml_fbograph.mcp_tools import get_kuzu_store
from xml_fbograph.storage.kuzu_index import close_cached_database, _is_connection_closed_error

def test():
    ref_file = r"e:\mcp_fbo\xml_fbograph\tests\test_data\v2\controllers\Dir\AI.xml"
    store = get_kuzu_store(ref_file)
    
    # Force close it
    close_cached_database(store.db_path)
    
    try:
        # This will call execute_cypher which should auto-reconnect
        res = store.execute_cypher("MATCH (n:XmlFile) RETURN count(*)")
        print("Success:", res)
    except Exception as e:
        print("Failed!")
        traceback.print_exc()
        print("is_connection_closed_error?", _is_connection_closed_error(e))

if __name__ == "__main__":
    test()
