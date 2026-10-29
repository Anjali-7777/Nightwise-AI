import torch
import pytest
from backend.attention.scratch_attention import (
    ScratchMultiHeadAttention,
    ScratchScaledDotProductAttention,
    SinusoidalPositionalEncoding
)

def test_positional_encoding_shape():
    d_model = 64
    seq_len = 16
    pe = SinusoidalPositionalEncoding(d_model=d_model, max_seq_len=64)
    x = torch.zeros(2, seq_len, d_model)
    out = pe(x)
    assert out.shape == (2, seq_len, d_model)
    # Output should not be all zeros since positional signal was added
    assert not torch.allclose(out, x)

def test_scaled_dot_product_attention_shapes_and_sums():
    d_k = 16
    seq_len = 8
    num_heads = 4
    batch_size = 2

    attn = ScratchScaledDotProductAttention(d_k=d_k)
    Q = torch.randn(batch_size, num_heads, seq_len, d_k)
    K = torch.randn(batch_size, num_heads, seq_len, d_k)
    V = torch.randn(batch_size, num_heads, seq_len, d_k)

    context, weights = attn(Q, K, V, causal_mask=True)
    assert context.shape == (batch_size, num_heads, seq_len, d_k)
    assert weights.shape == (batch_size, num_heads, seq_len, seq_len)

    # Verify rows sum to 1.0
    row_sums = weights.sum(dim=-1)
    expected_ones = torch.ones_like(row_sums)
    assert torch.allclose(row_sums, expected_ones, atol=1e-5)

    # Verify causal mask: weights[..., i, j] == 0 for j > i
    for i in range(seq_len):
        for j in range(i + 1, seq_len):
            assert torch.all(weights[..., i, j] == 0.0)

def test_multi_head_attention_full_forward():
    d_model = 128
    num_heads = 8
    seq_len = 12
    batch_size = 2

    mha = ScratchMultiHeadAttention(d_model=d_model, num_heads=num_heads)
    x = torch.randn(batch_size, seq_len, d_model)

    output, weights = mha(x, causal_mask=True)
    assert output.shape == (batch_size, seq_len, d_model)
    assert weights.shape == (batch_size, num_heads, seq_len, seq_len)
