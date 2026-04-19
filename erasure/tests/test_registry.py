"""Tests for the broker registry loader."""

from erasure.brokers.registry import filter_brokers, load_brokers


def test_load_brokers():
    brokers = load_brokers()
    assert len(brokers) > 500
    assert all(b.name for b in brokers)


def test_filter_ca_registered():
    brokers = load_brokers()
    ca = filter_brokers(brokers, ca_registered=True)
    assert len(ca) > 500
    assert all(b.ca_registered for b in ca)


def test_filter_crucial_ca():
    brokers = load_brokers()
    result = filter_brokers(brokers, priority="crucial", ca_registered=True, limit=10)
    assert 1 <= len(result) <= 10
    assert all(b.priority == "crucial" for b in result)
    assert all(b.ca_registered for b in result)
    assert all(b.opt_out_url for b in result)


def test_filter_limit():
    brokers = load_brokers()
    result = filter_brokers(brokers, priority="crucial", limit=3)
    assert len(result) <= 3
