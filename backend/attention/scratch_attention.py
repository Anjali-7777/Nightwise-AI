import math
import torch
import torch.nn as nn
import torch.nn.functional as F

class SinusoidalPositionalEncoding(nn.Module):
    """
    Standard sinusoidal positional encoding from 'Attention Is All You Need' (Vaswani et al., 2017).
    PE(pos, 2i) = sin(pos / 10000^(2i/d_model))
    PE(pos, 2i+1) = cos(pos / 10000^(2i/d_model))
    """
    def __init__(self, d_model: int, max_seq_len: int = 512):
        super().__init__()
        self.d_model = d_model
        pe = torch.zeros(max_seq_len, d_model)
        position = torch.arange(0, max_seq_len, dtype=torch.float32).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2, dtype=torch.float32) * (-math.log(10000.0) / d_model))
        
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0)) # Shape: (1, max_seq_len, d_model)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x shape: (batch_size, seq_len, d_model)
        seq_len = x.size(1)
        return x + self.pe[:, :seq_len, :]

class ScratchScaledDotProductAttention(nn.Module):
    """
    Scaled Dot-Product Attention:
    Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k) + Mask) V
    """
    def __init__(self, d_k: int):
        super().__init__()
        self.d_k = d_k

    def forward(
        self,
        Q: torch.Tensor,
        K: torch.Tensor,
        V: torch.Tensor,
        causal_mask: bool = True
    ) -> tuple[torch.Tensor, torch.Tensor]:
        # Q, K, V shapes: (batch_size, num_heads, seq_len, d_k)
        scores = torch.matmul(Q, K.transpose(-2, -1)) / math.sqrt(self.d_k)
        
        if causal_mask:
            seq_len = Q.size(-2)
            # Create upper-triangular mask with -inf
            mask = torch.triu(torch.full((seq_len, seq_len), float('-inf'), device=Q.device), diagonal=1)
            scores = scores + mask

        # Softmax over the last dimension (keys)
        attn_weights = F.softmax(scores, dim=-1)
        # Handle possible NaN if fully masked
        attn_weights = torch.nan_to_num(attn_weights, nan=0.0)
        
        # Context vectors: (batch_size, num_heads, seq_len, d_k)
        output = torch.matmul(attn_weights, V)
        return output, attn_weights

class ScratchMultiHeadAttention(nn.Module):
    """
    Multi-Head Attention from scratch without nn.MultiheadAttention.
    Projects inputs to Queries, Keys, Values across h heads, applies attention,
    concatenates head outputs, and applies the final linear projection W_O.
    """
    def __init__(self, d_model: int = 64, num_heads: int = 4):
        super().__init__()
        assert d_model % num_heads == 0, "d_model must be divisible by num_heads"
        self.d_model = d_model
        self.num_heads = num_heads
        self.d_k = d_model // num_heads

        # Linear projections for Query, Key, Value
        self.W_q = nn.Linear(d_model, d_model, bias=False)
        self.W_k = nn.Linear(d_model, d_model, bias=False)
        self.W_v = nn.Linear(d_model, d_model, bias=False)
        
        # Final output projection
        self.W_o = nn.Linear(d_model, d_model, bias=False)
        self.attention = ScratchScaledDotProductAttention(self.d_k)

    def forward(
        self,
        x: torch.Tensor,
        causal_mask: bool = True,
        debug: bool = False
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """
        x: (batch_size, seq_len, d_model)
        Returns:
          output: (batch_size, seq_len, d_model)
          attn_weights: (batch_size, num_heads, seq_len, seq_len)
        """
        batch_size, seq_len, _ = x.shape
        if debug:
            print(f"[Input x shape]: {x.shape}")

        # 1. Project to Q, K, V
        Q = self.W_q(x)  # (batch_size, seq_len, d_model)
        K = self.W_k(x)
        V = self.W_v(x)

        # 2. Reshape into heads: (batch_size, num_heads, seq_len, d_k)
        Q = Q.view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        K = K.view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        V = V.view(batch_size, seq_len, self.num_heads, self.d_k).transpose(1, 2)
        if debug:
            print(f"[Q, K, V per head shape]: {Q.shape}")

        # 3. Scaled Dot-Product Attention
        context, attn_weights = self.attention(Q, K, V, causal_mask=causal_mask)
        if debug:
            print(f"[Attention weights shape]: {attn_weights.shape}")
            print(f"[Context shape before concat]: {context.shape}")

        # 4. Concatenate heads: (batch_size, seq_len, d_model)
        context = context.transpose(1, 2).contiguous().view(batch_size, seq_len, self.d_model)
        
        # 5. Output projection W_o
        output = self.W_o(context)
        if debug:
            print(f"[Output after W_o shape]: {output.shape}")

        return output, attn_weights

def run_scratch_demo(tokens: list[str]) -> dict:
    """Runs scratch attention on input tokens and returns matrices for UI comparison."""
    torch.manual_seed(42)
    seq_len = max(1, len(tokens))
    d_model = 64
    num_heads = 4
    
    # Random embedding matrix for demonstration
    embeddings = torch.randn(1, seq_len, d_model)
    pos_encoder = SinusoidalPositionalEncoding(d_model, max_seq_len=seq_len + 10)
    x = pos_encoder(embeddings)

    mha = ScratchMultiHeadAttention(d_model=d_model, num_heads=num_heads)
    mha.eval()
    with torch.no_grad():
        _, attn = mha(x, causal_mask=True)
    
    # attn shape: (1, num_heads, seq_len, seq_len)
    weights = attn[0].tolist() # [head][row][col]
    head_avg = attn[0].mean(dim=0).tolist()

    return {
        "num_heads": num_heads,
        "d_model": d_model,
        "d_k": d_model // num_heads,
        "heads": weights,
        "head_avg": head_avg
    }
