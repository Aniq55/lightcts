import argparse
import math
import time
from lightcts_model import *

import torch
import torch.nn as nn
import numpy as np

from util import *
import os


def evaluate(data, X, Y, model, evaluateL2, evaluateL1, batch_size):
    model.eval()
    total_loss = 0
    total_loss_l1 = 0
    n_samples = 0
    predict = None
    test = None

    for X, Y in data.get_batches(X, Y, batch_size, False):
        X = torch.unsqueeze(X,dim=1)
        X = X.transpose(2,3)
        with torch.no_grad():
            output = model(X)
        output = torch.squeeze(output)
        if len(output.shape)==1:
            output = output.unsqueeze(dim=0)
        if predict is None:
            predict = output
            test = Y
        else:
            predict = torch.cat((predict, output))
            test = torch.cat((test, Y))

        scale = data.scale.expand(output.size(0), data.m)
        total_loss += evaluateL2(output * scale, Y * scale).item()
        total_loss_l1 += evaluateL1(output * scale, Y * scale).item()
        n_samples += (output.size(0) * data.m)

    rse = math.sqrt(total_loss / n_samples) / data.rse
    rae = (total_loss_l1 / n_samples) / data.rae
    mae = total_loss_l1 / n_samples
    # mse = total_loss / n_samples
    # mae = mse
    
    rmse = math.sqrt(total_loss * n_samples) / data.rmse
    # rmse = 0

    predict = predict.data.cpu().numpy()
    Ytest = test.data.cpu().numpy()
    sigma_p = (predict).std(axis=0)
    sigma_g = (Ytest).std(axis=0)
    mean_p = predict.mean(axis=0)
    mean_g = Ytest.mean(axis=0)
    index = (sigma_g != 0)
    correlation = ((predict - mean_p) * (Ytest - mean_g)).mean(axis=0) / (sigma_p * sigma_g)
    correlation = (correlation[index]).mean()

    return rse, rae, correlation, mae, rmse

parser = argparse.ArgumentParser(description='PyTorch Time series forecasting')
parser.add_argument('--data', type=str, default='data/solar.txt',
                    help='location of the data file')
parser.add_argument('--optim', type=str, default='adam')
parser.add_argument('--L1Loss', type=bool, default=True)
parser.add_argument('--normalize', type=int, default=2)
parser.add_argument('--device',type=str,default='cuda:0',help='')
parser.add_argument('--nhid',type=float,default=32,help='embedding size')
parser.add_argument('--in_dim',type=int,default=1,help='inputs dimension')
parser.add_argument('--group',type=int,default=4,help='group')
parser.add_argument('--horizon', type=int, default=3)
parser.add_argument('--layers',type=int,default=2,help='number of layers')
parser.add_argument('--batch_size',type=int,default=32,help='batch size')
parser.add_argument('--lr',type=float,default=0.0005,help='learning rate')
parser.add_argument('--weight_decay',type=float,default=0.0001,help='weight decay rate')
parser.add_argument('--clip',type=int,default=5,help='clip')
parser.add_argument('--epochs',type=int,default=100,help='')
parser.add_argument('--step_size',type=int,default=100,help='step_size')
parser.add_argument('--checkpoint', type=str, default='model/best_model.pt')


args = parser.parse_args()
device = torch.device(args.device)
torch.set_num_threads(3)



data_dir = args.data

Data = DataLoaderS(data_dir, 0.6, 0.2, device, args.horizon, 168, args.normalize)
model = ttnet(hid_dim=args.nhid, layers=args.layers, group=args.group)
model = model.to(device)

print(args)

if args.L1Loss:
    criterion = nn.L1Loss(size_average=False).to(device)
else:
    criterion = nn.MSELoss(size_average=False).to(device)
evaluateL2 = nn.MSELoss(size_average=False).to(device)
evaluateL1 = nn.L1Loss(size_average=False).to(device)


with open(args.checkpoint, 'rb') as f:
    model = torch.load(f)

vtest_acc, vtest_rae, vtest_corr, vtest_mae, vtest_rmse = evaluate(Data, Data.valid[0], Data.valid[1], model, evaluateL2, evaluateL1,
                                     args.batch_size)
test_acc, test_rae, test_corr, test_mae, test_rmse = evaluate(Data, Data.test[0], Data.test[1], model, evaluateL2, evaluateL1,
                                     args.batch_size)
print("final test rse {:5.4f} | test rae {:5.4f} | test corr {:5.4f} | test mae {:5.4f} | test mae  {:5.4f} | test rmse  {:5.4f}".format(test_acc, test_rae, test_corr, test_mae, test_mae, test_rmse))
