import argparse,json,time,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[2]))
from ml.src.inference import predict
def main():
 p=argparse.ArgumentParser();p.add_argument('--epochs',type=int,default=5);a=p.parse_args(); f=Path('ml/data/route_requests.jsonl')
 if not f.exists(): __import__('runpy').run_path('ml/scripts/generate_dataset.py')
 rows=[json.loads(x) for x in f.read_text().splitlines()]; correct=sum(predict(r['text'])['intent']==r['label']['intent'] for r in rows); out={'epochs':a.epochs,'examples':len(rows),'intent_accuracy':correct/len(rows),'note':'fallback evaluation; install torch for learned checkpoint','created_at':time.time()}; Path('ml/checkpoints').mkdir(exist_ok=True);Path('ml/checkpoints/metrics.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
if __name__=='__main__':main()
