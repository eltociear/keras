# Copyright 2016 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ==============================================================================
"""Tests for Scikit-learn API wrapper."""

import warnings

import tensorflow.compat.v2 as tf

import numpy as np

import keras
from keras.testing_infra import test_utils
from keras.wrappers import scikit_learn

INPUT_DIM = 5
HIDDEN_DIM = 5
TRAIN_SAMPLES = 10
TEST_SAMPLES = 5
NUM_CLASSES = 2
BATCH_SIZE = 5
EPOCHS = 1


def build_fn_clf(hidden_dim):
    model = keras.models.Sequential()
    model.add(keras.layers.Dense(INPUT_DIM, input_shape=(INPUT_DIM,)))
    model.add(keras.layers.Activation("relu"))
    model.add(keras.layers.Dense(hidden_dim))
    model.add(keras.layers.Activation("relu"))
    model.add(keras.layers.Dense(NUM_CLASSES))
    model.add(keras.layers.Activation("softmax"))
    model.compile(
        optimizer="sgd", loss="categorical_crossentropy", metrics=["accuracy"]
    )
    return model


def assert_classification_works(clf):
    np.random.seed(42)
    (x_train, y_train), (x_test, _) = test_utils.get_test_data(
        train_samples=TRAIN_SAMPLES,
        test_samples=TEST_SAMPLES,
        input_shape=(INPUT_DIM,),
        num_classes=NUM_CLASSES,
    )

    clf.fit(x_train, y_train, batch_size=BATCH_SIZE, epochs=EPOCHS)

    score = clf.score(x_train, y_train, batch_size=BATCH_SIZE)
    assert np.isscalar(score) and np.isfinite(score)

    preds = clf.predict(x_test, batch_size=BATCH_SIZE)
    assert preds.shape == (TEST_SAMPLES,)
    for prediction in np.unique(preds):
        assert prediction in range(NUM_CLASSES)

    proba = clf.predict_proba(x_test, batch_size=BATCH_SIZE)
    assert proba.shape == (TEST_SAMPLES, NUM_CLASSES)
    assert np.allclose(np.sum(proba, axis=1), np.ones(TEST_SAMPLES))


def build_fn_reg(hidden_dim):
    model = keras.models.Sequential()
    model.add(keras.layers.Dense(INPUT_DIM, input_shape=(INPUT_DIM,)))
    model.add(keras.layers.Activation("relu"))
    model.add(keras.layers.Dense(hidden_dim))
    model.add(keras.layers.Activation("relu"))
    model.add(keras.layers.Dense(1))
    model.add(keras.layers.Activation("linear"))
    model.compile(
        optimizer="sgd", loss="mean_absolute_error", metrics=["accuracy"]
    )
    return model


def assert_regression_works(reg):
    np.random.seed(42)
    (x_train, y_train), (x_test, _) = test_utils.get_test_data(
        train_samples=TRAIN_SAMPLES,
        test_samples=TEST_SAMPLES,
        input_shape=(INPUT_DIM,),
        num_classes=NUM_CLASSES,
    )

    reg.fit(x_train, y_train, batch_size=BATCH_SIZE, epochs=EPOCHS)

    score = reg.score(x_train, y_train, batch_size=BATCH_SIZE)
    assert np.isscalar(score) and np.isfinite(score)

    preds = reg.predict(x_test, batch_size=BATCH_SIZE)
    assert preds.shape == (TEST_SAMPLES,)


class ScikitLearnAPIWrapperTest(tf.test.TestCase):
    def test_classify_build_fn(self):
        with self.cached_session():
            clf = scikit_learn.KerasClassifier(
                build_fn=build_fn_clf,
                hidden_dim=HIDDEN_DIM,
                batch_size=BATCH_SIZE,
                epochs=EPOCHS,
            )

            assert_classification_works(clf)

    def test_classify_class_build_fn(self):
        class ClassBuildFnClf:
            def __call__(self, hidden_dim):
                return build_fn_clf(hidden_dim)

        with self.cached_session():
            clf = scikit_learn.KerasClassifier(
                build_fn=ClassBuildFnClf(),
                hidden_dim=HIDDEN_DIM,
                batch_size=BATCH_SIZE,
                epochs=EPOCHS,
            )

            assert_classification_works(clf)

    def test_classify_inherit_class_build_fn(self):
        class InheritClassBuildFnClf(scikit_learn.KerasClassifier):
            def __call__(self, hidden_dim):
                return build_fn_clf(hidden_dim)

        with self.cached_session():
            clf = InheritClassBuildFnClf(
                build_fn=None,
                hidden_dim=HIDDEN_DIM,
                batch_size=BATCH_SIZE,
                epochs=EPOCHS,
            )

            assert_classification_works(clf)

    def test_regression_build_fn(self):
        with self.cached_session():
            reg = scikit_learn.KerasRegressor(
                build_fn=build_fn_reg,
                hidden_dim=HIDDEN_DIM,
                batch_size=BATCH_SIZE,
                epochs=EPOCHS,
            )

            assert_regression_works(reg)

    def test_regression_class_build_fn(self):
        class ClassBuildFnReg:
            def __call__(self, hidden_dim):
                return build_fn_reg(hidden_dim)

        with self.cached_session():
            reg = scikit_learn.KerasRegressor(
                build_fn=ClassBuildFnReg(),
                hidden_dim=HIDDEN_DIM,
                batch_size=BATCH_SIZE,
                epochs=EPOCHS,
            )

            assert_regression_works(reg)

    def test_regression_inherit_class_build_fn(self):
        class InheritClassBuildFnReg(scikit_learn.KerasRegressor):
            def __call__(self, hidden_dim):
                return build_fn_reg(hidden_dim)

        with self.cached_session():
            reg = InheritClassBuildFnReg(
                build_fn=None,
                hidden_dim=HIDDEN_DIM,
                batch_size=BATCH_SIZE,
                epochs=EPOCHS,
            )

            assert_regression_works(reg)

    def test_regressor_deprecated(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            scikit_learn.KerasRegressor(build_fn_reg)
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "KerasRegressor is deprecated" in str(w[-1].message)

    def test_classifier_deprecated(self):
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            scikit_learn.KerasClassifier(build_fn_clf)
            assert len(w) == 1
            assert issubclass(w[-1].category, DeprecationWarning)
            assert "KerasClassifier is deprecated" in str(w[-1].message)


if __name__ == "__main__":
    tf.test.main()
