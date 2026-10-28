"""Small from-scratch Transformer encoder; optional until torch is installed."""
try:
 import torch
 from torch import nn
 class SelfAttention(nn.Module):
  def __init__(self,d,h):
   super().__init__(); assert d%h==0; self.h=h; self.dk=d//h; self.q=nn.Linear(d,d); self.k=nn.Linear(d,d); self.v=nn.Linear(d,d); self.o=nn.Linear(d,d)
  def forward(self,x,mask=None):
   b,n,d=x.shape; q=self.q(x).view(b,n,self.h,self.dk).transpose(1,2); k=self.k(x).view(b,n,self.h,self.dk).transpose(1,2); v=self.v(x).view(b,n,self.h,self.dk).transpose(1,2); a=(q@k.transpose(-2,-1))/(self.dk**.5)
   if mask is not None:a=a.masked_fill(mask==0,float('-inf'))
   return self.o((a.softmax(-1)@v).transpose(1,2).reshape(b,n,d))
 class NightwiseEncoder(nn.Module):
  def __init__(self,vocab=256,d=128,h=4,layers=2,classes=2):
   super().__init__(); self.embedding=nn.Embedding(vocab,d); self.pos=nn.Embedding(64,d); self.blocks=nn.ModuleList([nn.ModuleList([SelfAttention(d,h),nn.LayerNorm(d),nn.Sequential(nn.Linear(d,256),nn.GELU(),nn.Linear(256,d)),nn.LayerNorm(d)]) for _ in range(layers)]); self.head=nn.Linear(d,classes)
  def forward(self,x):
   z=self.embedding(x)+self.pos(torch.arange(x.shape[1],device=x.device));
   for att,n1,ff,n2 in self.blocks:z=n1(z+att(z)); z=n2(z+ff(z))
   return self.head(z.mean(1))
except ImportError:
 class NightwiseEncoder:
  def __init__(self,*a,**k): raise RuntimeError('Install torch to train the custom Transformer')
