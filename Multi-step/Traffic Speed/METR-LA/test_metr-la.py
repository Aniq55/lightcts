import argparse
import util
from engine import trainer
from util import *

parser = argparse.ArgumentParser()
parser.add_argument('--device',type=str,default='cuda:0',help='')
parser.add_argument('--data',type=str,default='data/METR-LA',help='data path')
parser.add_argument('--adjdata',type=str,default='data/sensor_graph/adj_mx.pkl',help='adj data path')
parser.add_argument('--adjtype',type=str,default='doubletransition',help='adj type')
parser.add_argument('--seq_length',type=int,default=12,help='')
parser.add_argument('--nhid',type=int,default=48,help='')
parser.add_argument('--group',type=int,default=4,help='')
parser.add_argument('--in_dim',type=int,default=2,help='inputs dimension')
parser.add_argument('--batch_size',type=int,default=32,help='batch size')
parser.add_argument('--dropout',type=float,default=0.1,help='dropout rate')
parser.add_argument('--weight_decay',type=float,default=0.0001,help='weight decay rate')
parser.add_argument('--learning_rate',type=float,default=0.001,help='learning rate')
parser.add_argument('--checkpoint',type=str,default='/logs/best.pth')
args = parser.parse_args()

def main():
    device = torch.device(args.device)
    sensor_ids, sensor_id_to_ind, adj_mx = util.load_adj(args.adjdata, args.adjtype)
    dataloader = util.load_dataset(args.data, args.batch_size, args.batch_size, args.batch_size)
    scaler = dataloader['scaler']
    supports = [torch.tensor(i).to(device) for i in adj_mx]
    engine = trainer(scaler, args.in_dim, args.seq_length, args.nhid, args.dropout, args.learning_rate,
                     args.weight_decay, args.device, supports, args.group)
    engine.model.load_state_dict(torch.load(args.checkpoint))
    model = engine.model
    model.to(device)
    model.eval()
    outputs = []
    realy = []
    model.eval()
    for iter, (x, y) in enumerate(dataloader['test_loader'].get_iterator()):
        testx = torch.Tensor(x).to(device)
        testx = testx.transpose(1, 3)
        testy = torch.Tensor(y).to(device)
        testy = testy.transpose(1, 3)[:, :1, :, :]
        with torch.no_grad():
            preds = model(testx).transpose(1, 3)
        outputs.append(preds)
        realy.append(testy)

    yhat = torch.cat(outputs, dim=0)
    yhat = scaler.inverse_transform(yhat)
    realy = torch.cat(realy, dim=0)

    amae = []
    amape = []
    armse = []
    for i in range(12):
        pred = yhat[...,i]
        real = realy[...,i]
        metrics = util.metric(pred,real)
        log = 'Evaluate model on test data for horizon {:d}, Test MAE: {:.4f}, Test MAPE: {:.4f}, Test RMSE: {:.4f}'
        print(log.format(i+1, metrics[0], metrics[1], metrics[2]))
        amae.append(metrics[0])
        amape.append(metrics[1])
        armse.append(metrics[2])

    log = 'On average over 12 horizons, Test MAE: {:.4f}, Test MAPE: {:.4f}, Test RMSE: {:.4f}'
    print(log.format(*util.metric(yhat,realy)))

if __name__ == "__main__":
    main()
