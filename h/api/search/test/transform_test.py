# -*- coding: utf-8 -*-
import mock
import pytest

from h.api.search import transform


@pytest.mark.parametrize("ann_in,ann_out", [
    # Preserves the basics
    ({}, {}),
    ({"other": "keys", "left": "alone"}, {"other": "keys", "left": "alone"}),

    # Target field
    ({"target": "hello"}, {"target": "hello"}),
    ({"target": []}, {"target": []}),
    ({"target": ["foo", "bar"]}, {"target": ["foo", "bar"]}),
    ({"target": [{"foo": "bar"}, {"baz": "qux"}]},
     {"target": [{"foo": "bar"}, {"baz": "qux"}]}),
])
def test_prepare_noop_when_nothing_to_normalize(ann_in, ann_out):
    transform.prepare(ann_in)
    assert ann_in == ann_out


@pytest.mark.parametrize("ann_in,ann_out", [
    ({"target": [{"source": "giraffe"}]},
     {"target": [{"source": "giraffe", "scope": ["*giraffe*"]}]}),
    ({"target": [{"source": "giraffe"}, "foo"]},
     {"target": [{"source": "giraffe", "scope": ["*giraffe*"]},
                 "foo"]}),
])
def test_prepare_adds_scope_field(ann_in, ann_out, uri_normalize):
    transform.prepare(ann_in)
    assert ann_in == ann_out


@mock.patch('h.api.search.transform.models')
def test_prepare_copies_parents_scopes_into_replies(models):
    parent_annotation = {
        'id': 'parent_annotation_id',
        'target': [{'scope': 'https://example.com/annotated_article'}]
    }
    reply = {'references': [parent_annotation['id'], 'some other id']}
    models.Annotation.fetch.return_value = parent_annotation

    transform.prepare(reply)

    assert reply['target'] == parent_annotation['target']


@mock.patch('h.api.search.transform.models')
def test_prepare_overwrites_existing_targets_in_replies(models):
    parent_annotation = {
        'id': 'parent_annotation_id',
        'target': [{'scope': 'https://example.com/annotated_article'}]
    }
    reply = {
        'references': [parent_annotation['id'], 'some other id'],
        'target': ['this should be overwritten']
    }
    models.Annotation.fetch.return_value = parent_annotation

    transform.prepare(reply)

    assert reply['target'] == parent_annotation['target']


@mock.patch('h.api.search.transform.models')
def test_prepare_does_nothing_if_parents_target_is_not_a_list(models):
    """It should do nothing to replies if the parent's target isn't a list.

    If the annotation is a reply and its parent's 'target' is not a list then
    it should not modify the reply's 'target' at all.

    """
    parent_annotation = {
        'id': 'parent_annotation_id',
        'target': 'not a list'
    }
    reply = {
        'references': [parent_annotation['id'], 'some other id'],
        'target': mock.sentinel.target
    }
    models.Annotation.fetch.return_value = parent_annotation

    transform.prepare(reply)

    assert reply['target'] == mock.sentinel.target


@mock.patch('h.api.search.transform.models')
def test_prepare_does_not_copy_other_keys_from_targets(models):
    """Only the parent's scope should be copied into replies.

    Not any other keys that the parent's target might have.

    """
    parent_annotation = {
        'id': 'parent_annotation_id',
        'target': [{
            'scope': 'https://example.com/annotated_article',
            'foo': 'bar',
            'selector': {}
        }]
    }
    reply = {'references': [parent_annotation['id'], 'some other id']}
    models.Annotation.fetch.return_value = parent_annotation

    transform.prepare(reply)

    assert 'foo' not in reply['target']
    assert 'selector' not in reply['target']


@mock.patch('h.api.search.transform.models')
def test_prepare_does_not_copy_targets_that_are_not_dicts(models):
    """Parent's targets that aren't dicts shouldn't be copied into replies."""
    parent_annotation = {
        'id': 'parent_annotation_id',
        'target': ['not a dict', None, ['not', 'a', 'dict']]
    }
    reply = {'references': [parent_annotation['id'], 'some other id']}
    models.Annotation.fetch.return_value = parent_annotation

    transform.prepare(reply)

    assert reply['target'] == []


@mock.patch('h.api.search.transform.models')
def test_prepare_does_not_copy_targets_with_no_scope(models):
    """Parent's targets with no 'scope' should not be copied into replies."""
    parent_annotation = {
        'id': 'parent_annotation_id',
        # Target has no 'scope' key.
        'target': [{
            'foo': 'bar',
            'selector': {}
        }]
    }
    reply = {'references': [parent_annotation['id'], 'some other id']}
    models.Annotation.fetch.return_value = parent_annotation

    transform.prepare(reply)

    assert reply['target'] == []



@pytest.mark.parametrize("ann,nipsa", [
    ({"user": "george"}, True),
    ({"user": "georgia"}, False),
    ({}, False),
])
def test_prepare_sets_nipsa_field(ann, nipsa, has_nipsa):
    has_nipsa.return_value = nipsa
    transform.prepare(ann)
    if nipsa:
        assert ann["nipsa"] is True
    else:
        assert "nipsa" not in ann


@pytest.mark.parametrize("ann_in,ann_out", [
    # Preserves the basics
    ({}, {}),
    ({"other": "keys", "left": "alone"}, {"other": "keys", "left": "alone"}),

    # Target field
    ({"target": "hello"}, {"target": "hello"}),
    ({"target": []}, {"target": []}),
    ({"target": ["foo", "bar"]}, {"target": ["foo", "bar"]}),
    ({"target": [{"foo": "bar"}, {"baz": "qux"}]},
     {"target": [{"foo": "bar"}, {"baz": "qux"}]}),
])
def test_render_noop_when_nothing_to_remove(ann_in, ann_out):
    assert transform.render(ann_in) == ann_out


@pytest.fixture
def has_nipsa(request):
    patcher = mock.patch('h.api.nipsa.has_nipsa', autospec=True)
    request.addfinalizer(patcher.stop)
    return patcher.start()


@pytest.fixture
def uri_normalize(request):
    patcher = mock.patch('h.api.uri.normalize', autospec=True)
    func = patcher.start()
    func.side_effect = lambda x: "*%s*" % x
    request.addfinalizer(patcher.stop)
    return func
