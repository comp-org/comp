"use strict";

import ReactDOM from "react-dom";
import React from "react";
import { BrowserRouter, Route, Switch } from "react-router-dom";
import axios from "axios";

import { InputsForm } from "./InputsForm";

axios.defaults.xsrfHeaderName = "X-CSRFTOKEN";
axios.defaults.xsrfCookieName = "csrftoken";

const domContainer = document.querySelector("#inputs-container");

class InputsApp extends React.Component {
  constructor(props) {
    super(props);
    this.doSubmit = this.doSubmit.bind(this);
    this.fetchInitialValues = this.fetchInitialValues.bind(this);
    this.resetInitialValues = this.resetInitialValues.bind(this);
  }

  fetchInitialValues() {
    const username = this.props.match.params.username;
    const app_name = this.props.match.params.app_name;
    console.log(this.props.match, this.isEditPage);
    if (this.type === "inputs") {
      return axios
        .get(`/${username}/${app_name}/api/v1/inputs/`)
        .then(function(response) {
          console.log(response);
          return response.data;
        })
        .catch(function(error) {
          console.log(error);
          alert("Something went wrong while fetching the inputs.");
        });
    } else if (this.props.type === "edit") {
      let model_pk = this.props.match.params.model_pk;
      console.log("in the edit block");
      return axios
        .all([
          axios.get(`/${username}/${app_name}/api/v1/inputs/`),
          axios.get(`/${username}/${app_name}/api/v1/${model_pk}/edit/`)
        ])
        .then(
          axios.spread((inputsResp, detailResp) => {
            console.log("inputsResp", inputsResp);
            console.log("detailResp", detailResp);
            let data = inputsResp.data;
            data["userInputs"] = {
              adjustment: detailResp.data.adjustment,
              meta_parameters: detailResp.data.meta_parameters
            };
            return data;
          })
        )
        .catch(error => {
          console.log(error);
          alert("Something went wrong while fetching the inputs");
        });
    } else {
      console.log(`type: ${this.props.type} is not allowed.`);
    }
  }

  resetInitialValues(metaParameters) {
    const username = this.props.match.params.username;
    const app_name = this.props.match.params.app_name;
    return axios
      .post(`/${username}/${app_name}/api/v1/inputs/`, metaParameters)
      .then(function(response) {
        console.log(response);
        return response.data;
      })
      .catch(function(error) {
        console.log(error);
      });
  }

  doSubmit(data) {
    const username = this.props.match.params.username;
    const app_name = this.props.match.params.app_name;
    console.log("posting...");
    console.log(data);
    return axios
      .post(`/${username}/${app_name}/api/v1/`, data)
      .then(function(response) {
        console.log(response);
        return response;
        // window.location.replace("/");
      });
  }

  render() {
    const username = this.props.match.params.username;
    const app_name = this.props.match.params.app_name;
    const id = `${username}/${app_name}`;
    return (
      <InputsForm
        fetchInitialValues={this.fetchInitialValues}
        resetInitialValues={this.resetInitialValues}
        initialValues={null}
        submitType="Create"
        doSubmit={this.doSubmit}
      />
    );
  }
}

ReactDOM.render(
  <BrowserRouter>
    <Switch>
      <Route
        exact
        path="/:username/:app_name/"
        render={routeProps => <InputsApp type="inputs" {...routeProps} />}
      />
      <Route
        exact
        path="/:username/:app_name/:model_pk/edit/"
        render={routeProps => <InputsApp type="edit" {...routeProps} />}
      />
    </Switch>
  </BrowserRouter>,
  domContainer
);
