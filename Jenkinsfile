#!/usr/bin/env groovy

node {

  def zbranch = 'ce-5.3'
  stage('Checkout') {
    checkout scm
  }

  stage('Build') {
    docker.image('zenoss/build-tools:0.0.10').inside() { 
      sh "make build IN_DOCKER= BRANCH=${zbranch}"
    }
  }

  stage('Publish') {
    def remote = [:]
    withFolderProperties {
      withCredentials( [sshUserPrivateKey(credentialsId: 'PUBLISH_SSH_KEY', keyFileVariable: 'identity', passphraseVariable: '', usernameVariable: 'userName')] ) {
        remote.name = env.PUBLISH_SSH_HOST
        remote.host = env.PUBLISH_SSH_HOST
        remote.user = userName
        remote.identityFile = identity
        remote.allowAnyHosts = true

        def tar_ver = sh( returnStdout: true, script: "awk '/^VERSION/{print \$3}' makefile" ).trim()
        sshPut remote: remote, from: "prodbin-${tar_ver}-${zbranch}.tar.gz", into: env.PUBLISH_SSH_DIR
      }
    }
  }

}
