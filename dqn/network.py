import math

import numpy as np
import tensorflow as tf
from tensorflow.python.framework import dtypes
from tensorflow.python.ops import random_ops
FLAGS = tf.app.flags.FLAGS

class DQNetwork:
    def __init__(self, nb_actions, scope):
        with tf.variable_scope(scope):

            self.inputs = tf.placeholder(
                shape=[None, FLAGS.resized_height, FLAGS.resized_width, FLAGS.agent_history_length], dtype=tf.float32,
                name="Input")

            conv1 = tf.contrib.layers.conv2d(
                self.inputs, FLAGS.conv1_nb_kernels, FLAGS.conv1_kernel_size, FLAGS.conv1_stride,
                activation_fn=tf.nn.relu, padding=FLAGS.conv1_padding, scope="conv1")
            conv2 = tf.contrib.layers.conv2d(
                conv1, FLAGS.conv2_nb_kernels, FLAGS.conv2_kernel_size, FLAGS.conv2_stride, padding=FLAGS.conv2_padding,
                activation_fn=tf.nn.relu, scope="conv2")

            hidden = tf.contrib.layers.fully_connected(
                inputs=tf.contrib.layers.flatten(conv2),
                num_outputs=FLAGS.fc_size,
                scope="fc1")

            summary_conv1_act = tf.contrib.layers.summarize_activation(conv1)
            self.image_summaries = []
            with tf.variable_scope('conv1'):
                tf.get_variable_scope().reuse_variables()
                weights = tf.get_variable('weights')
                grid = self.put_kernels_on_grid(weights)
                for i in range(FLAGS.agent_history_length):
                    self.image_summaries.append(
                        tf.summary.image('conv1/features/{}'.format(i), tf.expand_dims(grid[:, :, :, i], axis=3),
                                         max_outputs=1))

            summary_conv2_act = tf.contrib.layers.summarize_activation(conv2)

            summary_linear_act = tf.contrib.layers.summarize_activation(hidden)

            self.action_values = tf.contrib.layers.fully_connected(
                inputs=hidden,
                num_outputs=nb_actions,
                activation_fn=None, scope="value")

            summary_action_value_act = tf.contrib.layers.summarize_activation(self.action_values)

            if scope != 'target':

                self.actions = tf.placeholder(shape=[None], dtype=tf.int32)
                self.actions_onehot = tf.one_hot(self.actions, nb_actions, dtype=tf.float32)
                self.target_q = tf.placeholder(shape=[None], dtype=tf.float32)

                self.action_value = tf.reduce_sum(tf.multiply(self.action_values, self.actions_onehot), reduction_indices=1)

                # Loss functions
                self.action_value_loss = tf.reduce_sum(tf.square(self.target_q - self.action_value))

                self.optimizer = tf.train.AdamOptimizer(FLAGS.lr)
                grads = tf.gradients(self.action_value_loss, tf.trainable_variables())
                grads = list(zip(grads, tf.trainable_variables()))

                self.train_operation = self.optimizer.apply_gradients(grads)

                self.summaries = [summary_conv1_act, summary_conv2_act, summary_linear_act, summary_action_value_act]

                for grad, weight in grads:
                    self.summaries.append(tf.summary.histogram(weight.name + '_grad', grad))
                    self.summaries.append(tf.summary.histogram(weight.name, weight))

                self.merged_summary = tf.summary.merge(self.summaries)

    def put_kernels_on_grid(self, kernel, pad=1):

        '''Visualize conv. features as an image (mostly for the 1st layer).
        Place kernel into a grid, with some paddings between adjacent filters.
        Args:
          kernel:            tensor of shape [Y, X, NumChannels, NumKernels]
          (grid_Y, grid_X):  shape of the grid. Require: NumKernels == grid_Y * grid_X
                               User is responsible of how to break into two multiples.
          pad:               number of black pixels around each filter (between them)
        Return:
          Tensor of shape [(Y+2*pad)*grid_Y, (X+2*pad)*grid_X, NumChannels, 1].
        '''

        # get shape of the grid. NumKernels == grid_Y * grid_X
        def factorization(n):
            for i in range(int(sqrt(float(n))), 0, -1):
                if n % i == 0:
                    if i == 1: print('Who would enter a prime number of filters')
                    return (i, int(n / i))

        (grid_Y, grid_X) = factorization(kernel.get_shape()[3].value)
        print('grid: %d = (%d, %d)' % (kernel.get_shape()[3].value, grid_Y, grid_X))

        x_min = tf.reduce_min(kernel)
        x_max = tf.reduce_max(kernel)

        kernel1 = (kernel - x_min) / (x_max - x_min)

        # pad X and Y
        x1 = tf.pad(kernel1, tf.constant([[pad, pad], [pad, pad], [0, 0], [0, 0]]), mode='CONSTANT')

        # X and Y dimensions, w.r.t. padding
        Y = kernel1.get_shape()[0] + 2 * pad
        X = kernel1.get_shape()[1] + 2 * pad

        channels = kernel1.get_shape()[2]

        # put NumKernels to the 1st dimension
        x2 = tf.transpose(x1, (3, 0, 1, 2))
        # organize grid on Y axis
        x3 = tf.reshape(x2, tf.pack([grid_X, Y * grid_Y, X, channels]))

        # switch X and Y axes
        x4 = tf.transpose(x3, (0, 2, 1, 3))
        # organize grid on X axis
        x5 = tf.reshape(x4, tf.pack([1, X * grid_X, Y * grid_Y, channels]))

        # back to normal order (not combining with the next step for clarity)
        x6 = tf.transpose(x5, (2, 1, 3, 0))

        # to tf.image_summary order [batch_size, height, width, channels],
        #   where in this case batch_size == 1
        x7 = tf.transpose(x6, (3, 0, 1, 2))

        # scaling to [0, 255] is not necessary for tensorboard
        return x7

