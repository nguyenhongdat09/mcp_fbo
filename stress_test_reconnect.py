import sys
import threading
from pathlib import Path

sys.path.append(str(Path(__file__).parent.resolve()))

from xml_fbograph.query.engine import ensure_fresh_readonly_store, _store_cache, _graph_cache
from xml_fbograph.mcp_tools import get_kuzu_store, _kuzu_stores
from xml_fbograph.storage.kuzu_index import close_cached_database

def stress_test():
    ref_file = r"e:\mcp_fbo\xml_fbograph\tests\test_data\v2\controllers\Dir\AI.xml"
    
    import xml_fbograph.mcp_tools as mt
    
    def simulate_concurrent_requests():
        for i in range(20):
            try:
                store = mt.get_kuzu_store(ref_file)
                store.execute_cypher("MATCH (n:XmlFile) RETURN count(*)")
                
                # simulate external close occasionally
                if i % 5 == 0:
                    close_cached_database(store.db_path)
            except Exception as e:
                print(f"Error in request {i}: {e}")

    threads = []
    for _ in range(5):
        t = threading.Thread(target=simulate_concurrent_requests)
        t.start()
        threads.append(t)
        
    for t in threads:
        t.join()
        
    print("Stress test completed.")

if __name__ == "__main__":
    stress_test()
