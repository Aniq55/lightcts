import argparse
import time
import util
from util import *

from engine import trainer



parser = argparse.ArgumentParser()
parser.add_argument('--device',type=str,default='cuda:0',help='')
parser.add_argument('--seq_length',type=int,default=12,help='')
parser.add_argument('--nhid',type=int,default=64,help='')
parser.add_argument('--in_dim',type=int,default=1,help='inputs dimension')
parser.add_argument('--batch_size',type=int,default=64,help='batch size')
parser.add_argument('--learning_rate',type=float,default=0.002,help='learning rate')
parser.add_argument('--dropout',type=float,default=0.1,help='dropout rate')
parser.add_argument('--weight_decay',type=float,default=0.0001,help='weight decay rate')
parser.add_argument('--epochs',type=int,default=100,help='')
parser.add_argument('--group',type=float,default=4,help='g^t number')
parser.add_argument('--print_every',type=int,default=1000,help='')
parser.add_argument('--save',type=str,default='/home/chri6578/Documents/lightcts/logs/',help='save path')
parser.add_argument('--expid',type=int,default=4,help='experiment id')
parser.add_argument('--checkpoint',type=str,default=None)

args = parser.parse_args()

def main():
    device = torch.device(args.device)
    # adj_mx = get_adj_matrix('data/PEMS08/PEMS08.csv', 170)
    # dataloader = generate_data('data/PEMS08/PEMS08.npz', args.batch_size, args.batch_size)
    
    data_key = 'synth_01'
    with open(f"/home/chri6578/Documents/GG_SPP/markovspace/dataset/{data_key}.pkl", 'rb') as file:
        G_ = pickle.load(file)
    
    # adj_mx = get_adj_matrix('/home/chri6578/Documents/GG_SPP/markovspace/dataset/distance_01.csv', 20)
    dataloader = generate_data('/home/chri6578/Documents/GG_SPP/markovspace/dataset/data_01.npz', args.batch_size, args.batch_size)
    
    adj_mx = G_['A']
    
    scaler = dataloader['scaler']
    supports = [torch.tensor(i).to(device) for i in adj_mx]
    engine = trainer(scaler, args.in_dim, args.seq_length, args.nhid, args.dropout, args.learning_rate, args.weight_decay, args.device, supports, args.group)
    model = engine.model
    model.to(device)

    his_loss =[]
    val_time = []
    train_time = []
    for i in range(1,args.epochs+1):
        train_loss = []
        train_mape = []
        train_rmse = []
        t1 = time.time()
        dataloader['train_loader'].shuffle()
        for iter, (x, y) in enumerate(dataloader['train_loader'].get_iterator(),start=1):
            trainx = torch.Tensor(x).to(device)
            trainx= trainx.transpose(1, 3)
            trainy = torch.Tensor(y).to(device)
            trainy = trainy.transpose(1, 3)
            metrics = engine.train(trainx, trainy[:,0,:,:])
            train_loss.append(metrics[0])
            train_mape.append(metrics[1])
            train_rmse.append(metrics[2])
            if iter % args.print_every == 0:
                log = 'Iter: {:03d}, Train Loss: {:.4f}, Train MAPE: {:.4f}, Train RMSE: {:.4f}'
                print(log.format(iter, train_loss[-1], train_mape[-1], train_rmse[-1]),flush=True)
        t2 = time.time()
        train_time.append(t2-t1)
        valid_loss = []
        valid_mape = []
        valid_rmse = []
        s1 = time.time()
        for iter, (x, y) in enumerate(dataloader['val_loader'].get_iterator()):
            testx = torch.Tensor(x).to(device)
            testx = testx.transpose(1, 3)
            testy = torch.Tensor(y).to(device)
            testy = testy.transpose(1, 3)
            metrics = engine.eval(testx, testy[:,0,:,:])
            valid_loss.append(metrics[0])
            valid_mape.append(metrics[1])
            valid_rmse.append(metrics[2])
        s2 = time.time()
        log = 'Epoch: {:03d}, Inference Time: {:.4f} secs'
        print(log.format(i,(s2-s1)))
        val_time.append(s2-s1)
        mtrain_loss = np.mean(train_loss)
        mtrain_mape = np.mean(train_mape)
        mtrain_rmse = np.mean(train_rmse)
        mvalid_loss = np.mean(valid_loss)
        mvalid_mape = np.mean(valid_mape)
        mvalid_rmse = np.mean(valid_rmse)
        his_loss.append(mvalid_loss)
        log = 'Epoch: {:03d}\nTrain Loss: {:.4f}, Train MAPE: {:.4f}, Train RMSE: {:.4f}\nValid Loss: {:.4f}, Valid MAPE: {:.4f}, Valid RMSE: {:.4f}\nTraining Time: {:.4f}/epoch'
        print(log.format(i, mtrain_loss, mtrain_mape, mtrain_rmse, mvalid_loss, mvalid_mape, mvalid_rmse, (t2 - t1)),flush=True)
        torch.save(engine.model.state_dict(), args.save+"_epoch_"+str(i)+"_"+str(round(mvalid_loss,2))+".pth")
    bestid = np.argmin(his_loss)
    engine.model.load_state_dict(torch.load(args.save+"_epoch_"+str(bestid+1)+"_"+str(round(his_loss[bestid],2))+".pth"))
    engine.model.eval()

    outputs = []
    realy = []
    for iter, (x, y) in enumerate(dataloader['test_loader'].get_iterator()):
        testx = torch.Tensor(x).to(device)
        testx = testx.transpose(1,3)
        testy = torch.Tensor(y).to(device)
        testy = testy.transpose(1,3)[:,:1,:,:]
        with torch.no_grad():
            preds = engine.model(testx).transpose(1,3)
        outputs.append(preds)
        realy.append(testy)

    yhat = torch.cat(outputs,dim=0)
    yhat = scaler.inverse_transform(yhat)
    realy = torch.cat(realy,dim=0)
    amae = []
    amape = []
    armse = []
    print(yhat.shape, realy.shape)
    for i in range(12):
        pred = yhat[...,i]
        real = realy[...,i]
        metrics = util.metric(pred, real)
        log = 'Evaluate: Horizon {:d}, Test MAE: {:.4f}, Test MAPE: {:.4f}, Test RMSE: {:.4f}'
        print(log.format(i+1, metrics[0], metrics[1], metrics[2]))
        amae.append(metrics[0])
        amape.append(metrics[1])
        armse.append(metrics[2])

    log = 'On average over 12 horizons, Test MAE: {:.4f}, Test MAPE: {:.4f}, Test RMSE: {:.4f}'
    print(log.format(*util.metric(yhat, realy)))
    torch.save(engine.model.state_dict(), args.save+"_exp"+str(args.expid)+"_best_"+str(round(his_loss[bestid],2))+".pth")

if __name__ == "__main__":
    main()
