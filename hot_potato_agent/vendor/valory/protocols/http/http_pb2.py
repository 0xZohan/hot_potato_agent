# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: http.proto
"""Generated protocol buffer code."""
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
from google.protobuf.internal import builder as _builder

# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()


DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(
    b'\n\nhttp.proto\x12\x16\x61\x65\x61.valory.http.v1_0_0"\x91\x03\n\x0bHttpMessage\x12K\n\x07request\x18\x05 \x01(\x0b\x32\x38.aea.valory.http.v1_0_0.HttpMessage.Request_PerformativeH\x00\x12M\n\x08response\x18\x06 \x01(\x0b\x32\x39.aea.valory.http.v1_0_0.HttpMessage.Response_PerformativeH\x00\x1a\x63\n\x14Request_Performative\x12\x0e\n\x06method\x18\x01 \x01(\t\x12\x0b\n\x03url\x18\x02 \x01(\t\x12\x0f\n\x07version\x18\x03 \x01(\t\x12\x0f\n\x07headers\x18\x04 \x01(\t\x12\x0c\n\x04\x62ody\x18\x05 \x01(\x0c\x1aq\n\x15Response_Performative\x12\x0f\n\x07version\x18\x01 \x01(\t\x12\x13\n\x0bstatus_code\x18\x02 \x01(\x05\x12\x13\n\x0bstatus_text\x18\x03 \x01(\t\x12\x0f\n\x07headers\x18\x04 \x01(\t\x12\x0c\n\x04\x62ody\x18\x05 \x01(\x0c\x42\x0e\n\x0cperformativeb\x06proto3'
)

_globals = globals()
_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, _globals)
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, "http_pb2", _globals)
if _descriptor._USE_C_DESCRIPTORS == False:
    DESCRIPTOR._options = None
    _globals["_HTTPMESSAGE"]._serialized_start = 39
    _globals["_HTTPMESSAGE"]._serialized_end = 440
    _globals["_HTTPMESSAGE_REQUEST_PERFORMATIVE"]._serialized_start = 210
    _globals["_HTTPMESSAGE_REQUEST_PERFORMATIVE"]._serialized_end = 309
    _globals["_HTTPMESSAGE_RESPONSE_PERFORMATIVE"]._serialized_start = 311
    _globals["_HTTPMESSAGE_RESPONSE_PERFORMATIVE"]._serialized_end = 424
# @@protoc_insertion_point(module_scope)
