import threading

import tensorflow as tf
import random
import numpy as np
from agent import Agent
from envs.bandit_envs import TwoArms, ElevenArms
from network import ACNetwork
from baseline import RandomAgent
import multiprocessing
import concurrent.futures
import flags
import os
import sys
FLAGS = tf.app.flags.FLAGS


def recreate_directory_structure():
    if tf.gfile.Exists(FLAGS.results_val_file):
        os.remove(FLAGS.results_val_file)

    if not tf.gfile.Exists(FLAGS.checkpoint_dir):
        tf.gfile.MakeDirs(FLAGS.checkpoint_dir)
    else:
        if not FLAGS.resume and FLAGS.train:
            tf.gfile.DeleteRecursively(FLAGS.checkpoint_dir)
            tf.gfile.MakeDirs(FLAGS.checkpoint_dir)

    if not tf.gfile.Exists(FLAGS.frames_dir):
        tf.gfile.MakeDirs(FLAGS.frames_dir)
    else:
        if not FLAGS.resume and FLAGS.train:
            tf.gfile.DeleteRecursively(FLAGS.frames_dir)
            tf.gfile.MakeDirs(FLAGS.frames_dir)

    if not tf.gfile.Exists(FLAGS.summaries_dir):
        tf.gfile.MakeDirs(FLAGS.summaries_dir)
    else:
        if not FLAGS.resume and FLAGS.train:
            tf.gfile.DeleteRecursively(FLAGS.summaries_dir)
            tf.gfile.MakeDirs(FLAGS.summaries_dir)


def recreate_subdirectory_structure(settings):
    if not tf.gfile.Exists(settings["checkpoint_dir"]):
        tf.gfile.MakeDirs(settings["checkpoint_dir"])
    else:
        if not FLAGS.resume and FLAGS.train:
            tf.gfile.DeleteRecursively(settings["checkpoint_dir"])
            tf.gfile.MakeDirs(settings["checkpoint_dir"])

    if not tf.gfile.Exists(settings["frames_dir"]):
        tf.gfile.MakeDirs(settings["frames_dir"])
    else:
        if not FLAGS.resume and FLAGS.train:
            tf.gfile.DeleteRecursively(settings["frames_dir"])
            tf.gfile.MakeDirs(settings["frames_dir"])

    if not tf.gfile.Exists(settings["summaries_dir"]):
        tf.gfile.MakeDirs(settings["summaries_dir"])
    else:
        if not FLAGS.resume and FLAGS.train:
            tf.gfile.DeleteRecursively(settings["summaries_dir"])
            tf.gfile.MakeDirs(settings["summaries_dir"])


def run(settings):
    recreate_subdirectory_structure(settings)
    tf.reset_default_graph()

    with tf.device("/cpu:0"):
        global_step = tf.Variable(0, dtype=tf.int32, name='global_episodes', trainable=False)
        optimizer = tf.train.AdamOptimizer(learning_rate=settings["lr"])
        global_network = ACNetwork('global', None)

        num_agents = 1
        agents = []
        envs = []
        for i in range(num_agents):
            if settings["game"] == '11arms':
                this_env = ElevenArms()
            else:
                this_env = TwoArms(settings["game"])
            envs.append(this_env)

        for i in range(num_agents):
            agents.append(Agent(envs[i], i, optimizer, global_step, settings))
        saver = tf.train.Saver(max_to_keep=5)

    with tf.Session() as sess:
        coord = tf.train.Coordinator()
        if FLAGS.resume:
            ckpt = tf.train.get_checkpoint_state(settings["checkpoint_dir"])
            # print("Loading Model from {}".format(ckpt.model_checkpoint_path))
            try:
                saver.restore(sess, ckpt.model_checkpoint_path)
            except Exception as e:
                print(sys.exc_info()[0])
                print(e)
        else:
            sess.run(tf.global_variables_initializer())

        agent_threads = []
        for agent in agents:
            agent_play = lambda: agent.play(sess, coord, saver)
            thread = threading.Thread(target=agent_play)
            thread.start()
            agent_threads.append(thread)
        coord.join(agent_threads)


def thread_processing(lr, gamma, val_envs, game):

    model_name = "d_{}__lr_{}__gamma_{}".format(game, lr, gamma)
    print(model_name)
    checkpoint_dir = os.path.join(FLAGS.checkpoint_dir, model_name)
    summaries_dir = os.path.join(FLAGS.summaries_dir, model_name)
    frames_dir = os.path.join(FLAGS.frames_dir, model_name)

    settings = {"lr": lr,
                "gamma": gamma,
                "game": game,
                "model_name": model_name,
                "checkpoint_dir": checkpoint_dir,
                "summaries_dir": summaries_dir,
                "frames_dir": frames_dir,
                "envs": val_envs,
                "mode": "val"}

    run(settings)


def validate_hypertune():
    # recreate_directory_structure()

    model_instances = os.listdir(FLAGS.checkpoint_dir)
    lrs = [inst.split("__")[1].split("_")[1] for inst in model_instances]
    gammas = [inst.split("__")[2].split("_")[1] for inst in model_instances]

    game = model_instances[0].split("__")[0].split("_")[1]

    val_envs = TwoArms.get_envs(game, FLAGS.nb_test_episodes)

    with concurrent.futures.ThreadPoolExecutor(max_workers=multiprocessing.cpu_count()) as executor:
        for i in range(len(model_instances)):
            _ = executor.submit(thread_processing, lrs[i], gammas[i], val_envs, game)


if __name__ == '__main__':
    validate_hypertune()
